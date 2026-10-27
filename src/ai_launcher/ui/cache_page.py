"""The cache and scratch page, and the commands that share its logic.

Summary rows first (each a shortcut for a group), then the locations. Nothing
is deleted before the confirm step, which lists every path and the total.
All colour goes through ``PreviewFormatter``.

Author: Solent Labs™
"""

import re
import shutil
import subprocess  # nosec B404
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ai_launcher.core.cache_clean import (
    CleanContext,
    annotate,
    build_context,
    execute_plan,
    make_plan,
    summarize_results,
)
from ai_launcher.core.cache_data import (
    CLASS_UNREGISTERED,
    ROW_CACHES,
    ROW_DISK,
    ROW_SCRATCH,
    ROW_STALE,
    ROW_UNREGISTERED,
    SEVERITY_ATTENTION,
    SEVERITY_CRITICAL,
    SEVERITY_FINE,
    CacheEntry,
    CacheNotice,
    ItemResult,
    Plan,
    Registry,
    SummaryRow,
)
from ai_launcher.core.cache_notice import load_entries
from ai_launcher.core.cache_registry import current_platform, load_registry
from ai_launcher.core.cache_scan import (
    load_size_cache,
    peek_tree,
    refresh_sizes,
    size_cache_path,
)
from ai_launcher.core.cache_summary import GB, build_summary, read_disks, wsl_overcommit
from ai_launcher.core.scratch import (
    parse_duration,
    prune_candidates,
    tidy_empty_projects,
)
from ai_launcher.ui.formatter import PreviewFormatter
from ai_launcher.utils.humanize import humanize_size
from ai_launcher.utils.paths import fzf_preview_cmd

SYMBOLS = {3: "🔴", 2: "🟡", 1: "🟢", 0: "⚪"}
UNREGISTERED_ROWS_SHOWN = 10
UNREGISTERED_MIN_BYTES = 100 * 1024 * 1024
SEPARATOR = "─" * 77
ANSI = re.compile(r"\x1b\[[0-9;]*m")

fmt = PreviewFormatter()


def severity_symbol(severity: int) -> str:
    """The symbol for a severity; shown beside the colour, never instead of it."""
    return SYMBOLS.get(severity, "")


def _severity_color(severity: int) -> Tuple[str, ...]:
    return {
        SEVERITY_CRITICAL: (fmt.RED, fmt.BOLD),
        SEVERITY_ATTENTION: (fmt.YELLOW,),
        SEVERITY_FINE: (fmt.GREEN,),
    }.get(severity, (fmt.DIM,))


def strip_ansi(text: str) -> str:
    """Remove colour codes, for output that is not a terminal."""
    return ANSI.sub("", text)


def format_age(days: Optional[float]) -> str:
    """A short age: today, 12 days, 5 mo."""
    if days is None:
        return "?"
    if days < 1:
        return "today"
    if days < 100:
        return f"{int(days)} day{'s' if int(days) != 1 else ''}"
    return f"{int(days // 30)} mo"


def _size_text(entry: CacheEntry) -> str:
    if entry.size is None:
        return "…"
    text = humanize_size(entry.size_bytes)
    return f"≥ {text}" if entry.size.partial else text


def _disk_text(row: SummaryRow) -> str:
    parts = [
        f"{d.label} {d.percent_used:.0f}% full, {humanize_size(d.free)} free"
        for d in row.disks
    ]
    return " · ".join(parts) if parts else "free space unknown"


def _group_text(row: SummaryRow) -> str:
    """The middle column of a summary row."""
    size = humanize_size(row.total_bytes)
    if row.key == ROW_DISK:
        return _disk_text(row)
    if not row.count:
        return "nothing here"
    if row.key == ROW_SCRATCH:
        over = int(row.detail.get("over_critical", 0))
        extra = f", {over} over 10 GB" if over >= 2 else ""
        return f"{size} in {row.count} folder{'s' if row.count != 1 else ''}{extra}"
    if row.key == ROW_STALE:
        return f"{size} untouched for {int(row.detail.get('oldest_days', 0))}+ days"
    if row.key == ROW_CACHES:
        return f"{size} regenerable (browsers, npm, pip)"
    folders = f"{row.count} folder{'s' if row.count != 1 else ''}"
    return f"{size} in {folders} not in the registry"


def notice_text(notice: CacheNotice) -> str:
    """The launch notice as one line (no colour): what is wrong, then where to go."""
    size = humanize_size(notice.total_bytes)
    if notice.key == ROW_DISK and notice.disk is not None:
        disk = notice.disk
        name = "" if disk.label == "/" else f"{disk.label} "
        prefix = "" if "disk" in name else "Disk "
        what = f"{prefix}{name}{disk.percent_used:.0f}% full ({humanize_size(disk.free)} free)"
    elif notice.key == ROW_SCRATCH:
        what = f"{size} in {notice.count} scratch folders"
    elif notice.key == ROW_STALE:
        days = int(notice.detail.get("oldest_days", 0))
        what = f"Scratch untouched {days} days: {size}"
    else:
        what = f"{size} in unregistered cache folders"
    return f"{what} · ai-launcher cache"


def format_summary_row(row: SummaryRow) -> str:
    """One summary row, coloured by severity, with its symbol."""
    label = f"{severity_symbol(row.severity)} {row.key}"
    text = _group_text(row)
    if row.cleanable and row.cleanup_bytes:
        tail = f"clean up: {humanize_size(row.cleanup_bytes)}"
    elif row.key == ROW_UNREGISTERED and row.count:
        tail = "(report only)"
    else:
        tail = ""
    colors = _severity_color(row.severity)
    if row.key == ROW_UNREGISTERED or (not row.count and row.key != ROW_DISK):
        colors = (fmt.DIM,)
    line = f"{label:<15}{text:<46}{tail}"
    return fmt.paint(line.rstrip(), *colors)


def _action_text(entry: CacheEntry) -> str:
    if entry.blocked:
        return entry.blocked
    if entry.clean and shutil.which(entry.clean[0]):
        return " ".join(entry.clean)
    return ""


def format_entry_row(entry: CacheEntry, now: float) -> str:
    """One location row: name, size, age, class, what will happen."""
    cls = fmt.paint(
        f"{entry.cls:<12}",
        *{
            "clean": (fmt.GREEN,),
            "review": (fmt.YELLOW,),
        }.get(entry.cls, (fmt.DIM,)),
    )
    line = (
        f"  {entry.name[:30]:<30} {_size_text(entry):>10}  "
        f"{format_age(entry.age_days(now)):<9} {cls} {_action_text(entry)}"
    ).rstrip()
    if entry.blocked and entry.cls in ("review", "clean"):
        return fmt.paint(strip_ansi(line), fmt.DIM)
    return line


def rank_entries(
    entries: Sequence[CacheEntry], scratch_min_gb: float
) -> List[CacheEntry]:
    """Worth-attention entries first (big and deletable), each group by size."""
    floor = scratch_min_gb * GB

    def key(entry: CacheEntry) -> Tuple[int, int]:
        attention = entry.blocked is None and entry.size_bytes >= floor
        return (0 if attention else 1, -entry.size_bytes)

    return sorted(entries, key=key)


def build_choices(
    rows: List[SummaryRow], entries: List[CacheEntry], registry: Registry, now: float
) -> Tuple[List[str], Dict[str, SummaryRow], Dict[str, CacheEntry]]:
    """The fzf rows, and the maps from each row's key back to what it stands for.

    Each line is "key<TAB><TAB>text"; fzf shows only the text.
    """
    choices: List[str] = []
    row_map: Dict[str, SummaryRow] = {}
    entry_map: Dict[str, CacheEntry] = {}
    for row in rows:
        key = f"S:{row.key}"
        row_map[key] = row
        choices.append(f"{key}\t\t{format_summary_row(row)}")
    choices.append(f"__SEP__\t\t{fmt.paint(SEPARATOR, fmt.DIM)}")

    registered = [e for e in entries if e.cls != CLASS_UNREGISTERED]
    unregistered = [
        e
        for e in entries
        if e.cls == CLASS_UNREGISTERED and e.size_bytes >= UNREGISTERED_MIN_BYTES
    ]
    unregistered.sort(key=lambda e: -e.size_bytes)
    shown = unregistered[:UNREGISTERED_ROWS_SHOWN]
    for entry in rank_entries(registered, registry.notice.scratch_min_gb) + shown:
        if "\n" in str(entry.path) or "\t" in str(entry.path):
            continue  # a path that would break the row format is not offered
        key = f"E:{entry.path}"
        entry_map[key] = entry
        choices.append(f"{key}\t\t{format_entry_row(entry, now)}")
    hidden = len(unregistered) - len(shown)
    if hidden > 0:
        choices.append(
            f"__SEP__\t\t{fmt.paint(f'  …and {hidden} more not in the registry', fmt.DIM)}"
        )
    return choices, row_map, entry_map


def build_header(rows: List[SummaryRow], registry: Registry) -> str:
    """The lines above the list."""
    disk = next((r for r in rows if r.key == ROW_DISK), None)
    state = f" · {_disk_text(disk)}" if disk and disk.disks else ""
    lines = [
        fmt.paint("Cache and scratch", fmt.CYAN) + state,
        "Tab marks • Enter cleans what is marked, or the highlighted row • Esc leaves",
    ]
    if current_platform() == "wsl":
        lines.append(
            fmt.paint(
                "WSL: freed space stays inside WSL until the disk is compacted.",
                fmt.DIM,
            )
        )
        over = wsl_overcommit(disk.disks) if disk else None
        if over:
            wsl_disk, host = over
            lines.append(
                fmt.paint(
                    f"WSL's disk ({humanize_size(wsl_disk.total)}) is larger than "
                    f"{host.label} ({humanize_size(host.total)}): WSL can fill "
                    f"{host.label} before it reports low space.",
                    fmt.YELLOW,
                )
            )
    for warning in registry.warnings[:3]:
        lines.append(fmt.paint(f"! {warning}", fmt.YELLOW))
    lines.append(f"Registry additions: {registry.user_file}")
    return "\n".join(lines)


def expand_selection(
    keys: Sequence[str],
    row_map: Dict[str, SummaryRow],
    entry_map: Dict[str, CacheEntry],
) -> Tuple[List[CacheEntry], List[str]]:
    """Turn marked rows into entries. A summary row stands for its members.

    Returns:
        The entries, and notes for marked rows that have nothing to clean
    """
    entries: List[CacheEntry] = []
    notes: List[str] = []
    for key in keys:
        if key in entry_map:
            entries.append(entry_map[key])
        elif key in row_map:
            row = row_map[key]
            if row.cleanable:
                entries.extend(row.members)
            else:
                notes.append(f"{row.key}: nothing to clean from here")
    return entries, notes


def render_plan(plan: Plan) -> str:
    """The confirm screen: exactly what will happen, and what was left out."""
    lines = [
        fmt.paint(
            f"About to remove {len(plan.items)} location"
            f"{'s' if len(plan.items) != 1 else ''} ({humanize_size(plan.total_bytes)}):",
            fmt.BOLD,
        ),
        "",
    ]
    for item in plan.items:
        entry = item.entry
        cls = fmt.paint(
            f"{entry.cls:<7}", fmt.YELLOW if entry.cls == "review" else fmt.GREEN
        )
        command = entry.clean or item.argv
        what = (
            " ".join(command)
            if item.action == "command" and command
            else f"remove folder   {entry.path}"
        )
        lines.append(
            f"  {cls} {entry.name[:30]:<30} {humanize_size(entry.size_bytes):>9}   {what}"
        )
    if plan.skipped:
        skipped = ", ".join(f"{e.name} ({why})" for e, why in plan.skipped)
        lines += ["", fmt.paint(f"Skipped ({len(plan.skipped)}): {skipped}", fmt.DIM)]
    return "\n".join(lines)


def confirm_plan(
    plan: Plan,
    input_fn: Callable[[str], str] = input,
    is_tty: Optional[bool] = None,
    out: Callable[[str], None] = print,
    no_projects: bool = False,
) -> bool:
    """Show the plan and ask. The default is no; with nobody there, it is no."""
    out(render_plan(plan))
    if no_projects and plan.items:
        out(
            fmt.paint(
                "\nNo project folder was given, so only git repositories are protected. "
                "Pass your projects folder: ai-launcher cache ~/projects",
                fmt.YELLOW,
            )
        )
    if not plan.items:
        out("\nNothing to remove.")
        return False
    tty = sys.stdin.isatty() if is_tty is None else is_tty
    if not tty:
        out("\nNot a terminal: nothing was removed.")
        return False
    prompt = (
        'Type "delete" to confirm: '
        if plan.needs_typed_confirm
        else "Remove these? [y/N] "
    )
    try:
        answer = input_fn("\n" + prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return False
    if plan.needs_typed_confirm:
        return answer == "delete"
    return answer.lower() in ("y", "yes")


def render_results(results: Sequence[ItemResult]) -> str:
    """What happened, per row, and the total freed."""
    lines = []
    for result in results:
        if result.ok:
            lines.append(
                f"  {fmt.paint('✓', fmt.GREEN)} {result.entry.name}: freed "
                f"{humanize_size(result.freed_bytes)}"
            )
        else:
            lines.append(
                f"  {fmt.paint('✗', fmt.RED)} {result.entry.name}: {result.error}"
            )
    lines.append("")
    lines.append(
        fmt.paint(f"Freed {humanize_size(summarize_results(results))}", fmt.BOLD)
    )
    return "\n".join(lines)


# ------------------------------------------------------------ peek and preview


def render_peek(path: Path, now: Optional[float] = None) -> str:
    """The peek pane for a folder: names, sizes and counts, never contents."""
    now = now if now is not None else time.time()
    peek = peek_tree(path)
    total = peek.total
    newest = (now - total.newest_mtime) / 86400 if total.newest_mtime else None
    oldest = (now - total.oldest_mtime) / 86400 if total.oldest_mtime else None
    lines = [
        fmt.paint(str(path), fmt.CYAN),
        f"{humanize_size(total.size_bytes)} · {total.file_count:,} files · "
        f"newest {format_age(newest)} · oldest {format_age(oldest)}",
        "",
        fmt.paint("Largest", fmt.BOLD),
    ]
    for child in peek.children:
        name = child.name + ("/" if child.is_dir else "")
        age = (now - child.newest_mtime) / 86400 if child.newest_mtime else None
        lines.append(
            f"  {name[:34]:<34} {humanize_size(child.size_bytes):>9}  {format_age(age)}"
        )
    if peek.extensions:
        lines += ["", fmt.paint("By type", fmt.BOLD)]
        counts = sorted(peek.extensions.items(), key=lambda kv: -kv[1])[:8]
        lines.append("  " + " · ".join(f"{ext} {n:,}" for ext, n in counts))
    lines.append("")
    if total.partial:
        lines.append(fmt.paint("Cut short: the folder is large.", fmt.YELLOW))
    lines.append(fmt.paint("Names and sizes only; contents are never shown.", fmt.DIM))
    return "\n".join(lines)


def _rows_from_cache(registry: Registry) -> Tuple[List[CacheEntry], List[SummaryRow]]:
    entries = load_entries(registry, load_size_cache())
    annotate(entries, build_context([], registry.notice.in_use_minutes))
    return entries, build_summary(entries, registry.notice, read_disks(registry.notice))


def render_group(key: str, registry: Optional[Registry] = None) -> str:
    """The preview for a summary row: its members, from the size cache."""
    registry = registry or load_registry()
    _, rows = _rows_from_cache(registry)
    row = next((r for r in rows if r.key == key), None)
    if row is None:
        return ""
    lines = [format_summary_row(row), ""]
    if row.key == ROW_DISK:
        for disk in row.disks:
            lines.append(
                f"  {disk.label:<8} {disk.percent_used:.0f}% full · "
                f"{humanize_size(disk.free)} free of {humanize_size(disk.total)}"
            )
    for member in sorted(row.members, key=lambda e: -e.size_bytes)[:15]:
        lines.append(
            f"  {member.name[:30]:<30} {_size_text(member):>10}  {_action_text(member)}"
        )
    if row.cleanable:
        lines += ["", fmt.paint("Enter cleans every row above that can be.", fmt.DIM)]
    return "\n".join(lines)


def render_summary_preview(registry: Optional[Registry] = None) -> str:
    """The picker row's preview: the summary rows, read from the size cache."""
    registry = registry or load_registry()
    _, rows = _rows_from_cache(registry)
    lines = [fmt.paint("Cache and scratch", fmt.CYAN), ""]
    lines += [format_summary_row(r) for r in rows]
    lines += ["", fmt.paint("Enter opens the page.", fmt.DIM)]
    if not load_size_cache()["sizes"]:
        lines.append(fmt.paint("Sizes appear after the first scan.", fmt.DIM))
    return "\n".join(lines)


# ------------------------------------------------------------------- the page


def _clear() -> None:
    print("\033[H\033[2J", end="", flush=True)


def _run_fzf(choices: List[str], header: str, preview_cmd: str) -> Optional[List[str]]:
    """Show the list; return the marked lines, or None if the user left."""
    cmd = [
        "fzf",
        "--multi",
        "--ansi",
        "--prompt=Clean: ",
        "--height=100%",
        "--layout=reverse",
        "--border=rounded",
        "--border-label= Cache and scratch ",
        "--delimiter=\\t\\t",
        "--with-nth=2..",
        "--preview-window=right:45%:wrap:border-left",
        f"--preview={preview_cmd}",
        f"--header={header}",
        "--header-first",
        "--info=hidden",
    ]
    process = subprocess.Popen(  # nosec B603
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    out, _ = process.communicate(input="\n".join(choices).encode("utf-8"))
    if process.returncode != 0:
        return None
    return [
        line
        for line in out.decode("utf-8", errors="replace").split("\n")
        if line.strip()
    ]


def _refresh_with_progress(entries: List[CacheEntry], force: bool = False) -> None:
    def progress(entry: CacheEntry) -> None:
        print(f"\rScanning {entry.name[:40]:<40}", end="", flush=True)

    refresh_sizes(entries, size_cache_path(), force=force, progress=progress)
    print("\r" + " " * 60 + "\r", end="", flush=True)


def run_cache_page(
    project_paths: Sequence[Path] = (),
    registry: Optional[Registry] = None,
    fzf_runner: Callable[[List[str], str, str], Optional[List[str]]] = _run_fzf,
    input_fn: Callable[[str], str] = input,
    is_tty: Optional[bool] = None,
) -> None:
    """Run the page until the user leaves it. Returns when they do."""
    registry = registry or load_registry()
    ctx: CleanContext = build_context(project_paths, registry.notice.in_use_minutes)
    helper = Path(__file__).parent / "_cache_preview_helper.py"
    preview_cmd = fzf_preview_cmd(helper, "{}")

    while True:
        _clear()
        entries = load_entries(registry, {"sizes": {}})
        _refresh_with_progress(entries)
        annotate(entries, ctx)
        now = time.time()
        rows = build_summary(entries, registry.notice, read_disks(registry.notice), now)
        choices, row_map, entry_map = build_choices(rows, entries, registry, now)

        marked = fzf_runner(choices, build_header(rows, registry), preview_cmd)
        if marked is None:
            _clear()
            return
        keys = [line.split("\t\t", 1)[0] for line in marked]
        chosen, notes = expand_selection(keys, row_map, entry_map)
        _clear()
        for note in notes:
            print(note)
        if not chosen:
            if notes:
                input_fn("\nPress Enter to go back. ")
            continue

        plan = make_plan(chosen, ctx, now)
        if confirm_plan(plan, input_fn, is_tty, no_projects=not ctx.project_paths):
            print()
            results = execute_plan(
                plan, ctx, progress=lambda item: print(f"Cleaning {item.entry.name}…")
            )
            print(render_results(results))
            refresh_sizes([r.entry for r in results], size_cache_path(), force=True)
        try:
            input_fn("\nPress Enter to go back. ")
        except (EOFError, KeyboardInterrupt):
            return


def list_command(
    project_paths: Sequence[Path] = (), registry: Optional[Registry] = None
) -> None:
    """Print the same table as plain text. Nothing can be deleted from here."""
    registry = registry or load_registry()
    ctx = build_context(project_paths, registry.notice.in_use_minutes)
    entries = load_entries(registry, {"sizes": {}})
    refresh_sizes(entries, size_cache_path())
    annotate(entries, ctx)
    now = time.time()
    rows = build_summary(entries, registry.notice, read_disks(registry.notice), now)
    choices, _, _ = build_choices(rows, entries, registry, now)
    for choice in choices:
        print(strip_ansi(choice.split("\t\t", 1)[1]))
    for warning in registry.warnings:
        print(f"! {warning}")


def prune_command(
    older_than: str,
    dry_run: bool = False,
    yes: bool = False,
    input_fn: Callable[[str], str] = input,
    is_tty: Optional[bool] = None,
    registry: Optional[Registry] = None,
) -> int:
    """Remove old session scratch folders. Returns the process exit code.

    Only folders inside the launcher's own scratch folder are reachable. Without
    a terminal and without --yes nothing is removed.
    """
    try:
        seconds = parse_duration(older_than)
    except ValueError as error:
        print(f"Error: {error}")
        return 2
    registry = registry or load_registry()
    ctx = build_context([], registry.notice.in_use_minutes)
    plan = prune_candidates(seconds, ctx)
    print(render_plan(plan))
    if not plan.items:
        print("\nNothing to remove.")
        return 0
    if dry_run:
        print("\nDry run: nothing was removed.")
        return 0
    tty = sys.stdin.isatty() if is_tty is None else is_tty
    if not yes:
        if not tty:
            print("\nNot a terminal: nothing was removed. Use --yes to remove them.")
            return 1
        try:
            answer = input_fn("\nRemove these? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 1
        if answer not in ("y", "yes"):
            return 0
    results = execute_plan(plan, ctx)
    tidy_empty_projects()
    print(render_results(results))
    return 0 if all(r.ok for r in results) else 1


__all__ = [
    "build_choices",
    "build_header",
    "confirm_plan",
    "expand_selection",
    "format_age",
    "list_command",
    "notice_text",
    "prune_command",
    "render_group",
    "render_peek",
    "render_plan",
    "render_results",
    "render_summary_preview",
    "run_cache_page",
    "severity_symbol",
]
