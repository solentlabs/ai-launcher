# Cache and Scratch

> **Status:** Approved 2026-10-15. Implementation follows the order in
> [Documentation and Rollout](#documentation-and-rollout).

## Overview

AI agent sessions leave files behind: `.bak` copies, patches, logs, briefs, queue state, and the
caches of every tool they run (browsers, package managers, editor servers). Nothing in AI Launcher
or the tools themselves reports how much that adds up to. On one machine it filled a laptop's C:
drive to 98% before anyone noticed; about 50 GB of the WSL disk was `~/.cache`, and about 40 GB of
that was scratch from overnight sessions.

This feature does two things:

1. **A launch notice.** After you pick a project, one line in the launch box says when scratch or
   cache use is worth attention, and points to the page below. Otherwise it says nothing.
2. **A cache page** (`ai-launcher cache`). Lists the known locations with size, age and a safety
   class. You mark rows with Tab, see exactly what will be removed, and confirm. Nothing is deleted
   before that.

Optionally (see [Scratch Directory](#scratch-directory)) the launcher also gives each session a
place to put its scratch, so the next overnight run leaves one prunable folder, not a pile.

### Why the scope guard did not catch it

[Project Scope](project-scope.md) lets writes outside `~/projects` through unchecked, on purpose:
`/tmp` and `~/.bashrc` are not another project. That decision stands. The guard is about _which
project_ a session writes to; this feature is about _how much_ a session leaves behind. They are
separate problems and neither replaces the other.

### What already exists

Checked before writing this spec:

- No cache, scratch, size or disk-space reporting exists. Nothing in `src/` calls `disk_usage`.
- `--cleanup`, `--clean-provider`, `--clean-cache` and `--clean-npm` exist (`utils/cleanup.py`,
  `CleanupConfig`). They run **before launch, without a list or a confirmation**. `--clean-cache`
  deletes **every child of `~/.cache`**. That is the opposite of this feature's allowlist rule, and
  it is how the scratch in the incident above would have been wiped silently, along with every other
  tool's cache. See [Existing Flags](#existing-flags).
- `docs/configuration.md` says "There is no config file". This feature adds one, optional. See
  [Registry](#registry).
- The pieces to reuse: `humanize_size` / `format_time_ago` (`utils/humanize.py`), the fzf plumbing
  and preview-helper pattern (`ui/selector.py`, `ui/_preview_helper.py`), the launch box
  (`ui/startup_report.py`), `platformdirs` and `tomli` (already dependencies).

---

## Safety Rules

These are the constraints the rest of the design serves. They are enforced in code, in the module
that deletes, not by the registry's say-so. A registry entry can ask; it cannot override them.

1. **Allowlist only.** The deletable set is exactly the paths the registry resolves. A folder that
   merely looks like a cache is never offered for deletion.
2. **The tool's own clean command first.** Where a tool has one (`pip cache purge`,
   `uv cache clean`, `npm cache clean --force`, `pre-commit clean`), it is used. Removing the path
   is the fallback, and only where the entry says so.
3. **Agent scratch is "review before delete".** Mixed contents, may still be needed. Offered with a
   peek at what is inside, and never offered while a running session may be using it.
4. **Report-only, never deletable:** `~/.claude` (or `CLAUDE_CONFIG_DIR`), every discovered or
   manual project's working tree, the project the session was launched in, and anything inside or
   containing any of those. Computed at run time from the scan roots, not listed in the registry.
5. **Nothing is deleted without the confirm step.** It lists every path and the total. The default
   answer is no.
6. **Out of scope:** Docker and WSL disk compaction. Both need admin rights and do not belong in a
   launcher. See [Per-Platform Behavior](#per-platform-behavior) for how this shows up on WSL.

Deletion guards that hold whatever the registry says:

| Guard                                                                                                                                                         | Why                                              |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Path must be under the home directory (or the platform temp dir)                                                                                              | A bad user entry cannot reach `/etc`             |
| Never the home or temp folder, a drive root, or a top-level home folder that holds user data or the cache dir (`.cache`, `.config`, `.ssh`, `Documents`, ...) | `~` or `~/.cache` typed by mistake               |
| A location that is itself a symlink is report-only                                                                                                            | Preserve symlinks; do not delete a link's target |
| Inside a tree, symlinks are unlinked, never followed                                                                                                          | `rmtree` stays inside the tree                   |
| Protected set recomputed and in-use check rerun **at delete time**                                                                                            | The page may have been open for minutes          |
| No shell: clean commands run as an argv list, with a timeout                                                                                                  | No injection through a path or name              |

---

## Registry

The registry is data, not code: a TOML file of known locations. This follows the project invariant
that nothing is a hardcoded list.

| File                                                      | Role                                         |
| --------------------------------------------------------- | -------------------------------------------- |
| `src/ai_launcher/data/caches.toml` (ships in the package) | The defaults                                 |
| `<config dir>/caches.toml` (optional, user-owned)         | Your additions, overrides, notice thresholds |

`<config dir>` is `platformdirs.user_config_path("ai-launcher")`: `~/.config/ai-launcher/` on Linux
and WSL, `~/Library/Application Support/ai-launcher/` on macOS, `%LOCALAPPDATA%\ai-launcher\` on
Windows (the same directories [architecture.md](architecture.md#platform-specific-paths) lists). The
file is never created or edited by the launcher; the page prints its path. The package data file
must be added to `pyproject.toml` (`[tool.setuptools.package-data]`).

The same file holds one setting that is not about caches: `[update] check = true`, the opt-in daily
look for a newer release. See [Updating](updating.md#checking-automatically).

### Entry format

```toml
[[location]]
id        = "pip"                      # unique; a user entry with the same id replaces the default
name      = "pip cache"
group     = "package-cache"            # display grouping only
class     = "clean"                    # clean | review | report  (see below)
clean     = ["pip", "cache", "purge"]  # the tool's own command, argv list, no shell (optional)
remove    = true                       # may the path be removed if there is no clean command
                                       # or the tool is not installed (default false)
note      = "Wheels and HTTP cache; pip re-downloads as needed."
paths.linux   = ["{cache}/pip"]
paths.macos   = ["~/Library/Caches/pip"]
paths.windows = ["%LOCALAPPDATA%\\pip\\Cache"]
# paths.wsl falls back to paths.linux when absent
```

Agent scratch is a user entry, since the launcher cannot know what your tools name their folders. A
glob is allowed in the **last path component only** (the launcher's own `{scratch}/*/*`, project
then session, is the one pattern with two), and each match is a separate row named for the folder it
matched:

```toml
[[location]]
id     = "my-agent-scratch"
name   = "Agent scratch"
class  = "review"
remove = true
paths.linux = ["{cache}/my-agent-*"]
```

| Field        | Meaning                                                                                                                 |
| ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `class`      | `clean`: regenerable. `review`: mixed contents, peek first. `report`: never deleted                                     |
| `clean`      | argv list. Run only if `argv[0]` is on `PATH`. Never run through a shell                                                |
| `remove`     | Allow removing the path itself. Without `clean` or `remove`, the row is report-only                                     |
| `paths.<os>` | `linux`, `macos`, `windows`, `wsl`. `wsl` falls back to `linux`                                                         |
| path tokens  | `~`, `$VAR` / `%VAR%`, and `{cache}`: `XDG_CACHE_HOME` or `~/.cache` on Linux and WSL, the platform cache dir elsewhere |

An entry with an unknown key, a missing `id` or a path that fails the
[deletion guards](#safety-rules) is skipped and listed under the page header as a warning. It never
stops the launcher.

A user entry can lower a class (`clean` → `report`) but a default `report` entry stays `report`; the
protected set above is applied after the registry is loaded and wins over everything.

### Defaults shipped

Paths are what each tool documents; the macOS and Windows ones are **not yet verified on those
systems** (see open questions). Sizes are from the machine in the incident.

| Id                    | Linux / WSL               | Class  | Removed by                                         | Seen   |
| --------------------- | ------------------------- | ------ | -------------------------------------------------- | ------ |
| `playwright`          | `{cache}/ms-playwright`   | clean  | remove path                                        | 5.2 GB |
| `puppeteer`           | `{cache}/puppeteer`       | clean  | remove path                                        | 0.9 GB |
| `npm-cache`           | `~/.npm/_cacache`         | clean  | `npm cache clean --force`                          | 1.8 GB |
| `npm-npx`             | `~/.npm/_npx`             | clean  | remove path                                        | 1.5 GB |
| `pip`                 | `{cache}/pip`             | clean  | `pip cache purge`                                  | 0.5 GB |
| `uv`                  | `{cache}/uv`              | clean  | `uv cache clean`                                   | 0.5 GB |
| `pre-commit`          | `{cache}/pre-commit`      | clean  | `pre-commit clean`                                 | 1.8 GB |
| `vscode-server`       | `~/.vscode-server`        | report | not offered                                        | 2.0 GB |
| `claude-home`         | `~/.claude`               | report | never (protected)                                  | 1.6 GB |
| `claude-sessions`     | `~/.claude/projects`      | report | never (Claude cleans its own, `cleanupPeriodDays`) |        |
| `ai-launcher-scratch` | `<cache dir>/scratch/*/*` | review | remove path                                        | new    |

`~/.npm` is split on purpose: `npm cache clean --force` only empties `_cacache`, so a single
`~/.npm` row would report 3.2 GB and free about half of it. Each row's "freed" figure is measured
before and after, not assumed.

`vscode-server` is report-only in v1: removing it is safe but forces a reinstall of the server and
every extension on the next remote connect, which is not what someone clearing disk usually wants.
See open questions.

Docker's disk image and Windows Temp are not defaults. Docker is out of scope; Windows Temp is on
the Windows side of WSL (see [Per-Platform Behavior](#per-platform-behavior)).

### Unregistered folders

Everything under the cache directory that the registry does not name is summed and the largest
children are listed as **report-only** rows marked `unregistered`. They are never deletable. They
exist because the incident's scratch was exactly this: big, unnamed, and invisible. To manage one,
add a registry entry; to silence it, add the same entry with `class = "report"`.

---

## Scan and Size Performance

Large trees must not slow launch. The rule: **the launch path reads a cache file and never walks a
tree.**

### Size cache

`<state dir>/cache-sizes.json` (`platformdirs.user_state_path("ai-launcher")`, mode 0600). Per
location: path, size, file count, newest modification time, when it was scanned, and whether the
walk was cut short.

- Written atomically (temp file, then rename). Two launchers at once is safe: the newer `scanned_at`
  wins per location.
- A size is **fresh** for 6 hours. The notice uses whatever is in the file, fresh or not, so a stale
  number still raises a notice. Only the page insists on fresh numbers.
- Missing or unreadable cache file: no size-based notice. The free-disk rule still works, since it
  needs no walk.

### The walk

One function, used by the page, the refresh and the preview:

- Iterative `os.scandir`; never follows symlinks (a symlink counts as the link).
- Disk use is `st_blocks * 512` on POSIX and `st_size` on Windows. Hard links are counted once, by
  `(st_dev, st_ino)`, because npm, uv and pnpm caches are full of them. On Windows, `os.scandir`
  entries carry no link count or inode, so a hard-linked file counts once per link there: a size can
  read high, never low.
- Newest modification time is taken from every file seen, so the age of a folder is its newest file,
  not the folder's own mtime (which only changes when a direct child is added or removed).
- A time budget per location (10 s). A walk that runs out reports what it has, marked "≥ 12 GB" and
  flagged partial. Python 3.8 compatible; no extra dependencies.
- Errors (permission denied, a file vanishing mid-walk) are skipped, not raised.

### When it runs

| Where               | What                                                                                                                |
| ------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Launcher start      | A daemon thread refreshes stale locations while the picker is open, then exits. Writes each location as it finishes |
| `ai-launcher cache` | Rescans stale locations before drawing, with a progress line                                                        |
| Launch box notice   | Reads the cache file only. One `disk_usage` call. Target: under 10 ms                                               |

A thread, not a detached process: the picker keeps the user in the launcher for seconds to minutes,
which is the time the walk needs, and a thread dies with the launcher, so it can leave nothing
running behind. If the user picks fast, the notice uses the previous numbers and the thread is
dropped; nothing is half-written because the file is replaced only at a location's end.

The very first launch has no sizes, so the notice can only be the free-disk one. From the second
launch on, the sizes are there.

---

## Launch Notice

Shown in the launch box, between the scope line and the context sources:

```text
│ 📁 Project:  ~/projects/solentlabs/utilities/ai-launcher                           │
│ 🔒 Scope:    writes to other projects ask first                                    │
│ 💾 Cache:    41 GB in 3 scratch folders, oldest 12 days · ai-launcher cache        │
```

One line, at most about 70 characters so it fits the 85-column box. It appears for every provider
(the box is shared) and not in the Shell row of the Open With list (that path has no box).

### Rules

The notice fires if **any** rule holds. If several do, the first in this order is shown:

| #   | Rule                                                                                     | Default                       | Line                                              |
| --- | ---------------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------- |
| 1   | Low free disk                                                                            | under 5% free, or under 10 GB | `Disk 98% full (6.7 GB free) · ai-launcher cache` |
| 2   | Many scratch folders: `review`-class locations of at least 1 GB each, at least 2 of them | 1 GB, 2 folders               | `41 GB in 3 scratch folders, oldest 12 days · …`  |
| 3   | Stale scratch: any `review`-class location of at least 1 GB untouched for over 7 days    | 1 GB, 7 days                  | `Scratch untouched 12 days: 14 GB · …`            |
| 4   | Unregistered cache folders add up                                                        | 5 GB                          | `38 GB in unregistered cache folders · …`         |

Decisions:

- **Rule 3 is scratch only.** A browser or package cache is old by nature (Playwright's 5 GB may not
  change for months) and would nag at every launch. Only scratch, which should not outlive a task,
  counts as stale.
- **Rule 4 exists because of the incident.** The scratch there was in no registry, so rules 2 and 3
  could not see it. Rule 4 is the only one that does, and registering a folder (even as `report`)
  removes it from the sum.
- **Rule 1 on WSL checks the Windows drive too.** `df /` inside WSL reports the virtual disk's own
  size: on the machine in the incident, 882 GB free on `/` while `C:` (`/mnt/c`) was 98% full. The
  rule checks `/` and, on WSL, each folder in `notice.extra_disk_paths` (default `["/mnt/c"]`), and
  fires on the worst one. The line names the disk.
- **At most once per 24 hours** per rule, so a condition you have seen and chosen to live with does
  not repeat at every launch. The time of the last notice per rule is kept in the size cache file.
  `interval_hours = 0` shows it every launch.
- **Quiet otherwise**, and quiet on error. Any exception in the notice is swallowed (logged at debug
  level): a bug here must not stop a session starting, as with the scope guard.

The notice is data first: `core/cache_notice.py` returns a `CacheNotice` dataclass (rule, numbers),
and the launch box formats it. Providers and the notice code contain no strings meant for display,
and no raw ANSI (project invariants 1 and 2).

### Thresholds

All in the optional `caches.toml`, all with defaults, none required:

```toml
[notice]
enabled              = true
interval_hours       = 24
min_free_percent     = 5
min_free_gb          = 10
scratch_min_gb       = 1
scratch_min_count    = 2
stale_days           = 7
unregistered_min_gb  = 5
# critical tier, used by the page's summary rows (see The Page)
critical_scratch_gb  = 10
critical_stale_days  = 30
critical_free_percent = 2
critical_free_gb     = 3
extra_disk_paths     = ["/mnt/c"]   # default only on WSL
```

---

## The Page

`ai-launcher cache [PATH ...]` is a top-level command, not a provider subcommand: it is not about
any one tool. `PATH` is optional and repeatable; scan roots are what the protected set is computed
from, so pass the same ones you launch with. `--manual-paths` works as it does elsewhere. A `--list`
flag prints the same table as plain text (no fzf, nothing deletable), like `--list` and `--discover`
do for projects.

### Where it is reached from

| From                                   | How                                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------- |
| The project picker                     | A row below Configuration: `💾 Cache and scratch`, with the worst severity's symbol |
| The launch notice                      | It names the command, `ai-launcher cache`                                           |
| The shell, a script or a scheduled job | `ai-launcher cache`, `cache --list`, `scratch prune`                                |

The picker row works like the Configuration row's neighbours: Enter opens the page, and leaving the
page (Esc) returns to the picker with the cursor where it was. The picker handles it itself, as it
does a rescan, so `Selection` and `cli.py` are unchanged. The row's symbol and its preview pane (the
summary rows, without the list) are read from the size-cache file, so the picker still does no
walking. `select_project()` already has the scan paths and manual paths the protected set needs.

### Layout

Summary rows come first. They are the screen's way of saying "this is the problem, and here is the
one-key fix". Below them, the individual locations.

```text
Cache and scratch · C: 98% full (6.7 GB free)
Tab marks • Enter cleans what is marked, or the highlighted row • Esc leaves
─────────────────────────────────────────
> 🔴 DISK        C: 98% full, 6.7 GB free
  🔴 SCRATCH     41 GB in 3 folders, 2 over 10 GB           clean up: 32.9 GB
  🟡 STALE       14 GB untouched for 12+ days               clean up: 14.2 GB
  🟢 CACHES      11.8 GB regenerable (browsers, npm, pip)   clean up: 11.8 GB
  ⚪ UNREGISTERED  38 GB in 31 folders not in the registry  (report only)
─────────────────────────────────────────
    my-agent-2026-10-03   14.2 GB  12 days   review
    my-agent-2026-10-06    9.8 GB   9 days   review
    my-agent-overnight     8.1 GB  in use    review   not offered
    ms-playwright          5.2 GB  40 days   clean
    pre-commit             1.8 GB  22 days   clean    pre-commit clean
    npm cache (_cacache)   1.8 GB   2 days   clean    npm cache clean --force
    ~/.claude              1.6 GB   today    report   never deleted
```

Columns in the location rows: name, size (`≥` if partial), age (newest file), class, and what will
happen (a tool command, or blank for "remove folder"). The list is an ordinary fzf list with
`--multi` and `--ansi`, built the way the project selector is: choices on stdin as UTF-8 bytes,
header from a string, preview from a helper script (`ui/_cache_preview_helper.py`, run as a
subprocess like `_preview_helper.py`). All colour goes through `PreviewFormatter` (invariant 2).

### Summary rows

A summary row is a **shortcut for a group of rows**, not a location. It is how the page makes
cleaning easy: put the cursor on `SCRATCH`, press Enter, and the confirm step lists every deletable
scratch folder, with the total.

| Row          | Group it stands for                                  | Cleaning it                            |
| ------------ | ---------------------------------------------------- | -------------------------------------- |
| DISK         | None: the state of the disk                          | Nothing to clean; shown first when bad |
| SCRATCH      | Every `review`-class location                        | All that are not in use                |
| STALE        | `review`-class locations untouched for `stale_days`+ | All that are not in use                |
| CACHES       | Every `clean`-class location                         | All, by each tool's own command first  |
| UNREGISTERED | Folders in the cache dir the registry does not name  | Not cleanable; add a registry entry    |

Each row has a **severity**, shown as a colour and a symbol (colour alone is not enough: some
terminals and some eyes lose it):

| Severity  | Symbol | Colour | Meaning                                                           |
| --------- | ------ | ------ | ----------------------------------------------------------------- |
| critical  | 🔴     | red    | Out of control: act now                                           |
| attention | 🟡     | yellow | Worth attention: the same thresholds that raise the launch notice |
| fine      | 🟢     | green  | Nothing to flag; the row is still there so a clean-up is one key  |
| report    | ⚪     | dim    | Information only                                                  |

| Row          | attention (yellow)                      | critical (red)                               |
| ------------ | --------------------------------------- | -------------------------------------------- |
| DISK         | under 5% free or under 10 GB            | under 2% free or under 3 GB                  |
| SCRATCH      | 2+ folders of 1 GB+ (notice rule 2)     | 10 GB+ in total, or any one folder of 10 GB+ |
| STALE        | 1 GB+ untouched 7+ days (notice rule 3) | 1 GB+ untouched 30+ days                     |
| CACHES       | never                                   | never (caches are meant to be big)           |
| UNREGISTERED | 5 GB+ (notice rule 4)                   | never (it cannot be cleaned from here)       |

These are the **same numbers as the launch notice**, with a second, higher tier. The notice shows
the most severe row's line; a critical row makes the notice line red. A summary row that is `fine`
or has nothing to clean is still drawn (dimmed when empty), so the layout does not jump around. The
WSL disk row shows both disks, `/` and `C:`, and takes the worse one's severity.

Rows are ordered most severe first. The thresholds are in `[notice]`, with four new keys:
`critical_scratch_gb = 10`, `critical_stale_days = 30`, `critical_free_percent = 2`,
`critical_free_gb = 3`.

A summary row is not a special key: Tab marks it like any row, Enter on it cleans it, and several
can be marked together. At the confirm step each is expanded into its member locations, the in-use,
report-only and guard checks are applied to each member (so `SCRATCH` never includes the folder a
session is writing to), and anything skipped is listed with its reason. Marking `SCRATCH` and one of
its folders does not list that folder twice.

### Ranking

Summary rows first, most severe first. Then the locations in two groups, each sorted by size,
largest first:

1. **Worth attention:** locations that would raise the notice on their own (a scratch folder of 1 GB
   or more untouched for over 7 days, or any location of 1 GB or more that is not in use).
2. **Everything else.**

Rows that cannot be deleted (report-only, in use, symlink, tool missing and no `remove`) stay in the
list, so the picture is complete and they can be peeked at. They are dimmed, with the reason in the
last column.

### Keys

| Key       | On                      | Result                                                                                  |
| --------- | ----------------------- | --------------------------------------------------------------------------------------- |
| Tab       | a summary or a location | Marks or unmarks it (fzf's multi-select, as elsewhere)                                  |
| Enter     | the list                | Goes to the confirm step with the marked rows, or the highlighted row if none is marked |
| Esc       | the list                | Leaves. Nothing is touched                                                              |
| Esc / `n` | the confirm step        | Back to the list                                                                        |

Enter on `DISK` or `UNREGISTERED` has nothing to clean; it says so and returns to the list. If a row
that cannot be deleted is marked, it is dropped at the confirm step and listed there as "skipped",
with its reason. The list does not try to stop the mark: fzf cannot refuse a Tab, and a row that
refuses to mark with no explanation would be worse.

### Peek

The preview pane is the "peek". For any row it shows, without reading file contents:

- the path, class, size, newest and oldest modification time, file count;
- the 15 largest children (name, size, age);
- counts by extension (`.bak` 412, `.log` 88, `.patch` 31, …).

File **names and sizes only**, never contents: scratch holds briefs and queue state that may contain
anything. The peek has its own 3-second budget and says so if it is cut short. `report` rows get the
same pane, which is how you see what is inside `~/.claude` (1.6 GB) without any way to delete it.

### In-use check

A `review` row is **not offered** when any of these holds, and the row says why:

1. **Lock.** A launcher-managed session folder contains a `.ai-launcher-session` file with the
   session's PID. If that process is alive, the folder is in use. A dead PID means a stale file,
   which is ignored.
2. **Recent modification.** Any file in the tree was modified in the last `in_use_minutes` (default
   120, in `[scratch]`). This is the only check for folders the launcher does not manage, and it is
   the same walk that sizes the folder, so it costs nothing extra on the page.

Both are a heuristic: a session idle for three hours is not seen. That is why scratch is `review`,
not `clean`, and why the confirm step names every path.

The PID check must not use `os.kill(pid, 0)` on Windows: there it terminates the process. It uses
`OpenProcess` and `GetExitCodeProcess` through `ctypes`, and `os.kill(pid, 0)` only on POSIX.

The in-use check is **rerun at delete time**, not trusted from when the page was drawn.

---

## Deletion Flow

```text
 list ──Enter──> confirm ──yes──> delete each ──> summary ──> list (sizes rescanned)
   ↑                │ no / Esc
   └────────────────┘
```

1. **Plan.** The marked rows are turned into a plan: for each, the protected set, the in-use check
   and the deletion guards are applied. Rows that fail are in "skipped" with a reason.
2. **Confirm.** A plain screen, not fzf, listing exactly what will happen:

   ```text
   About to remove 3 locations (24.3 GB):

     review  my-agent-2026-10-03   14.2 GB   remove folder   ~/.cache/my-agent-2026-10-03
     clean   ms-playwright          5.2 GB   remove folder   ~/.cache/ms-playwright
     clean   pre-commit             1.8 GB   pre-commit clean

   Skipped (2): my-agent-overnight (in use), ~/.claude (never deleted)

   Remove these? [y/N]
   ```

   A `review` row in the plan changes the last line to `Type "delete" to confirm:`. A `clean` row is
   regenerable, so `y` is enough; a `review` row may hold the only copy of something.

3. **Delete.** One at a time: the tool's own command if there is one and it is installed, else the
   folder if `remove` is set. Failures are recorded and the rest continue.
4. **Summary.** Per row: freed (measured: size before minus size after), or the error. A total. Then
   back to the list with sizes rescanned, so what was left is visible.

The default answer is no, an empty answer is no, and a non-terminal stdin is no: the flow never
deletes without a person at the keyboard. (`scratch prune --yes` is the one explicit exception; see
below.)

Clean commands run with a 300-second timeout (the existing `--clean-npm` uses 10, which is too short
for a multi-GB cache); a timeout is a failure, not a hang.

---

## Scratch Directory

**Recommendation: v1, together with `scratch prune`.** They are one feature: the prune command has
nothing to manage without the directory, and the directory is the only part of this design that
prevents the problem rather than reporting it.

### Behavior

At launch the launcher creates a folder for the session and tells the session about it:

```text
<cache dir>/scratch/<project>/<YYYYMMDD-HHMMSS>-<pid>/
```

- `<cache dir>` is `platformdirs.user_cache_path("ai-launcher")`. `<project>` is the project's
  folder name with anything outside letters, digits, `-` and `_` replaced by `_`.
- The environment variable **`AI_SCRATCH_DIR`** is set to that path for the tool's process, for
  every provider (environment is inherited, so providers need no code for it).
- Claude Code additionally gets one sentence appended to the system prompt the scope guard already
  appends: where to put `.bak` files, patches, logs and briefs, and that the folder may be removed
  once the session ends. Other tools get the variable only.
- The folder is created at launch and removed at exit if it is still empty. A `.ai-launcher-session`
  file in it holds the PID, and is removed at exit.
- The folder is added to the scope guard's exempt list, so a scan root that contains the cache
  directory never makes scratch writes ask.

**It can only be asked for, not enforced**, the same limit the scope guard states. A session may
ignore the instruction, and a tool may not read the variable. The launch box says
`Scratch: $AI_SCRATCH_DIR → ~/.cache/ai-launcher/scratch/…`, so it is visible what was asked.

The Shell row of the Open With list sets no scratch directory (no session, no instruction).

### Protecting what is worth keeping

Scratch is disposable by instruction only, so the design assumes a session will sometimes put
something useful there. Nothing is removed unless a person asks, and what is asked is narrow:

- **The launcher never removes a non-empty scratch folder on its own.** At exit it removes the
  folder only if it is empty. There is no automatic expiry, no prune at launch, and `--cleanup` does
  not touch it.
- **The prompt says what scratch is for.** The sentence given to Claude Code names scratch as
  throwaway (`.bak` copies, patches, logs, briefs) and says anything worth keeping goes in the
  project, not in `$AI_SCRATCH_DIR`. Other tools get only the variable, so the launch box shows the
  path and the note.
- **`scratch prune` has no default age.** `--older-than` is required, so there is no age the tool
  picks for you.
- **The age is by last write, and in-use folders are never candidates** (see
  [In-use check](#in-use-check)).
- **The list and total come before any deletion**, and `--yes` is the only way around the question.
- **The page treats these folders as `review`:** peek first, typed `delete` to confirm.
- **Nothing outside the managed folder is reachable from `scratch prune`.**

What this does not cover: a file a session wrote to scratch against the prompt, in a folder you
confirm after the age you chose. The peek lists file names, sizes and extension counts so you can
spot a `.md` or `.db` among the logs, but it is your confirmation that stops the removal.

### `scratch prune`

```bash
ai-launcher scratch prune --older-than 14d [--dry-run] [--yes]
```

- Candidates are session folders **inside `<cache dir>/scratch/` only**. Nothing else is reachable
  from this command, whatever the registry says.
- "Older" is the newest modification time in the folder, not its creation time; a folder written to
  yesterday is not 14 days old.
- Durations are `<n>h`, `<n>d` or `<n>w`. Anything else is an error, not a default.
- A folder in use (PID alive, or modified within `in_use_minutes`) is never a candidate. The current
  session's folder is excluded by that rule.
- Lists the candidates and the total, then asks `Remove these? [y/N]`. `--dry-run` stops after the
  list. `--yes` skips the question, and is **required** when stdin is not a terminal: without a
  person and without `--yes`, it removes nothing and exits non-zero.
- Exit 0 when it removed something or had nothing to remove; non-zero on an error.

It shares the plan and delete code with the page; the only difference is that its candidates come
from one folder, not the registry.

---

## Existing Flags

`--clean-cache` removes every child of `~/.cache` before launch, with no list and no confirmation.
That cannot coexist with "allowlist only" in the same tool, and it is a trap next to this feature:
the page lists what would be lost, the flag loses it silently.

**Decided: remove `--clean-cache`** (and `CleanupConfig.clean_system_cache`) in the release that
adds this, with the reason in the changelog and in [architecture.md](architecture.md), and point its
users at `ai-launcher cache`. A deprecation period only keeps the trap armed. `--clean-npm` calls
the tool's own command, so it is not a conflict and stays. `--cleanup` and `--clean-provider`
(Claude's backup files, debug logs, old CLI versions) are provider maintenance, not caches, and stay
as they are.

---

## Per-Platform Behavior

| Area            | Linux                          | macOS              | WSL                             | Windows                                         |
| --------------- | ------------------------------ | ------------------ | ------------------------------- | ----------------------------------------------- |
| Registry paths  | `paths.linux`                  | `paths.macos`      | `paths.wsl`, else `paths.linux` | `paths.windows`                                 |
| `{cache}`       | `XDG_CACHE_HOME` or `~/.cache` | `~/Library/Caches` | as Linux                        | `%LOCALAPPDATA%`                                |
| Size            | `st_blocks`                    | `st_blocks`        | `st_blocks`                     | `st_size`                                       |
| Free-disk rule  | `/`                            | `/`                | `/` **and `/mnt/c`**            | the system drive                                |
| PID liveness    | `os.kill(pid, 0)`              | same               | same                            | `OpenProcess` (never `os.kill`)                 |
| Background walk | thread                         | thread             | thread                          | thread                                          |
| Clean commands  | argv, no shell                 | same               | same                            | same; `.cmd` shims resolved with `shutil.which` |

Notes:

- **WSL: freeing space inside WSL does not shrink `C:`.** The virtual disk (`ext4.vhdx`) only grows
  until compacted, which is out of scope. The page footer on WSL says so, and shows free space on
  both the Linux filesystem and `C:`, so a deletion that "freed 40 GB" and left `C:` at 98% is not a
  surprise. Sparse-disk and compaction how-tos belong in docs, not the launcher.
- **WSL: nothing on the Windows side is scanned in v1.** `/mnt/c` is a network-speed filesystem
  (9P); a walk there would be slow, and Windows Temp is not part of the AI-tool ecosystem. The
  Windows drive is only read for free space. Native Windows has a `windows-temp` default entry.
- **Windows: `cmd.exe` and UNC paths** are not a concern here (no shell is started), but a registry
  path on a UNC share is walked like any other and may be slow; the time budget applies.
- **macOS and native Windows paths are written from each tool's documentation and have not been run
  on those systems.** They are verified before release; see the open questions.
- Symlink-creating tests skip where symlinks cannot be created, as the existing ones do.

---

## Where It Sits in the Stack

```text
cli.py                      cache [PATH...]  ·  scratch prune
   │                         │
   │ select_project() ─────> ui/cache_page.py   (picker row; loops back to the picker)
   │ launch_ai()             ↓
   │   scratch dir made      ui/cache_page.py ── fzf list, preview helper, confirm
   │   AI_SCRATCH_DIR set    │
   │   notice evaluated      ↓
   ↓                        core/cache_clean.py     plan + guards + delete
display_launch_info(notice)  │      ↑ protected set from scan roots / manual projects
   ↑                         ↓
core/cache_notice.py ──────> core/cache_scan.py     walk, size cache, in-use check, peek
   │   core/cache_summary.py ↑   severity rows, shared by the notice and the page
   │   core/scratch.py           session folder, AI_SCRATCH_DIR, prune
   │                         ↑
   └── CacheNotice (data)    core/cache_registry.py  data/caches.toml + user caches.toml
                             core/cache_data.py      CacheLocation, CacheEntry, Plan (dataclasses)
```

- Core modules return dataclasses and make no display decisions. `ui/` formats, through
  `PreviewFormatter` for anything coloured.
- `utils/humanize.py` supplies sizes and ages. `utils/session.py` has a second `format_time_ago`;
  the new code uses the one in `humanize.py` and does not add a third.
- The provider interface gains nothing: `AI_SCRATCH_DIR` travels in the environment, and the one
  Claude sentence rides on the system prompt it already builds.

---

## Tests

Tests ship with the code. Table-driven where the body repeats
([CONTRIBUTING.md](../CONTRIBUTING.md#test-structure-table-driven-or-fixture-driven)), with `ids=`.

**Every test runs against a fake home** (`tmp_path` with `HOME`, `USERPROFILE`, `XDG_CACHE_HOME` and
`LOCALAPPDATA` pointed into it) and fails if a path outside it is touched. A test must never reach
the developer's real `~/.cache`.

| File                          | Covers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_cache_registry.py`      | Defaults load and are valid. Per-platform resolution, `wsl`→`linux` fallback. Token expansion. User entry replaces by `id`. Unknown keys, missing `id`, bad globs, a `class` lowered or not raised: skipped with a warning, never raised. Glob only in last component                                                                                                                                                                                                                 |
| `test_cache_scan.py`          | Sizes against a built tree. Hard links counted once. Symlinks not followed (a link to a huge folder adds nothing). Newest mtime. Budget cut-off gives partial. Permission error skipped. Size cache round-trip, atomic write, corrupt file ignored                                                                                                                                                                                                                                    |
| `test_cache_notice.py`        | Each rule at, just under and just over its threshold. Priority order. 24-hour interval. WSL checks `/mnt/c`. **No `scandir` call at all in the notice path** (patched to raise). Any exception returns no notice                                                                                                                                                                                                                                                                      |
| `test_cache_clean.py`         | **Safety:** hostile registries (`/`, `~`, `..`, home, a scan root, a project, `~/.claude`, a path with a symlinked leaf, a glob matching a project) produce an empty plan. The plan is a subset of the registry's resolved paths. Report-only never planned. In-use rechecked at delete time. Commands run as argv with `shell=False`, with the exact argv. Missing tool falls back to `remove` only if set. A failing command or rmtree does not stop the rest. Freed bytes measured |
| `test_cache_in_use.py`        | PID alive and dead; stale session file ignored; recent mtime; the Windows path never calls `os.kill`                                                                                                                                                                                                                                                                                                                                                                                  |
| `test_cache_page.py`          | fzf mocked as in `test_selector.py`: summary rows (severity at, under and over each tier, symbol as well as colour, empty group dimmed), Enter on a summary row expands to its members without duplicates and still applies the in-use and report-only checks, ranking, header numbers, non-deletable dimmed, marked-but-skipped reported, confirm default no, empty answer no, non-tty no, `review` needs the typed word, Esc leaves with nothing deleted                            |
| `test_selector.py` (extended) | Cache row below Configuration, symbol follows severity, Enter opens the page and returns to the picker, Esc in the page returns with nothing deleted, the row's preview reads only the size cache (no walk), picker still returns a `Selection` for projects                                                                                                                                                                                                                          |
| `test_cache_preview.py`       | Peek shows names and sizes, never file contents; extension counts; budget message                                                                                                                                                                                                                                                                                                                                                                                                     |
| `test_scratch.py`             | Dir created and removed when empty; `AI_SCRATCH_DIR` set for every provider; Claude prompt sentence; session file; exempt from the scope guard; Shell row sets nothing                                                                                                                                                                                                                                                                                                                |
| `test_scratch_prune.py`       | `--older-than` parsing (valid, invalid, zero); only the managed dir is reachable even with a hostile registry; in-use and current session excluded; `--dry-run` removes nothing; no tty without `--yes` removes nothing and exits non-zero                                                                                                                                                                                                                                            |
| `test_cli.py` (extended)      | `cache`, `cache --list`, `scratch prune` wired; `--clean-cache` gone                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `test_startup_report*.py`     | Notice line in the launch box, fits 85 columns with a long path and a long name                                                                                                                                                                                                                                                                                                                                                                                                       |

Targets, from CONTRIBUTING: new code at least 80% (aiming at 90% for `cache_clean`, since it is the
code that deletes), data structures 100%, formatters 95%. Patch coverage on the Codecov comment is a
blocker. Coverage floors come from `make validate-ci`, not a local run.

**Rendered checks** (type checks do not catch box overflow): the launch box with each notice rule;
the page at 80, 100 and 200 columns; the confirm screen with a 120-character path. On this machine,
run the page with `HOME` pointed at a fixture that copies the incident's shape (many
`~/.cache/my-agent-*` folders, a Playwright dir, a hard-linked npm tree), never at the real home.

---

## Documentation and Rollout

Order, following the project's habit: docs, then failing tests, then code, then the bash decision.

1. This spec, reviewed and approved.
2. Docs from it: a `docs/cache-and-scratch.md` user section split out of this spec as
   [project-scope.md](project-scope.md) is for the scope guard; an architecture.md section ("Cache
   and Scratch") with the decisions below; `configuration.md` (the new command, the optional
   `caches.toml`, and "There is no config file" corrected); README feature list; `docs/README.md`
   index; `project-scope.md` (one row: scratch dir is exempt); CHANGELOG.
3. Failing tests for each module above.
4. Code, one module at a time, `make validate-ci` green.
5. Bash prototype: **recommend no port**. It needs TOML parsing, the size cache and the PID check;
   the scope guard is already Python-only for the same reason. The divergence is noted in the
   changelog (project invariant 4).

Nothing is staged or committed by this work; the maintainer stages and approves each commit.

---

## Decisions

- **Report widely, delete narrowly.** The page shows the whole ecosystem and the unregistered
  remainder; it can only delete what the registry names, and `report` rows have no delete path.
- **The registry is data, with defaults in the package and additions in the user's file.** No
  provider or tool list in code (invariant 3). The file is optional; the launcher works without it.
- **Safety rules live in the deleting module, not in the registry.** A wrong user entry cannot
  weaken them.
- **Sizes come from a cache, never from the launch path.** Launch reads one small file.
- **Thread, not a detached process, for the background walk.** Nothing is left running after the
  launcher exits.
- **Scratch is `review`, caches are `clean`.** Different confirmation strength for different
  consequences.
- **The page is a picker row as well as a command.** The launch notice appears after the picker has
  gone, so the picker is the only screen you see on every launch that can point at the page.
- **Notice rules are scratch-only for "stale".** Old caches are normal; old scratch is the problem.
- **A notice at most once a day per rule.** A condition you chose to live with stops nagging.
- **No `--clean-cache`.** See [Existing Flags](#existing-flags).
- **Peek shows names, not contents.** Scratch may hold secrets.
- **No Docker or WSL compaction.** Needs admin rights; the page says what deletion does and does not
  free on WSL instead.

---

## Decided

- The page is also a picker row below Configuration (see
  [Where it is reached from](#where-it-is-reached-from)).
- `AI_SCRATCH_DIR` and `scratch prune` ship in v1 with the page, with the safeguards in
  [Protecting what is worth keeping](#protecting-what-is-worth-keeping).
- `--clean-cache` is removed in the release that adds this feature (see
  [Existing Flags](#existing-flags)).
- An optional `caches.toml` in the user's config directory is acceptable; `configuration.md` is
  corrected when this ships.
- On approval, the recommended answer was taken for the remaining questions: no bash prototype port
  (divergence noted in the changelog); `in_use_minutes = 120`; `~/.vscode-server` report-only;
  nothing on the Windows side scanned from WSL; typed `delete` for `review` rows and `y/N` for
  `clean` rows; the unregistered rows and notice rule 4 included; the `AI_SCRATCH_DIR` line shown in
  the launch box; a critical row makes the launch notice line red.
- The critical tiers stand: 10 GB scratch, 30 days stale, under 2% or 3 GB free.

## Open Questions

1. Can the macOS and Windows default paths be checked on those systems before release? They are
   written from each tool's documentation and are unverified.
