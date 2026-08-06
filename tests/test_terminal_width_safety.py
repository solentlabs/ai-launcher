"""Tests that shipped glyphs measure the same width in fzf and in the terminal.

fzf lays out the preview pane with go-runewidth, which scores a variation
selector (U+FE0F) as zero-width and an East Asian *Neutral* base as one column.
Terminals honour the selector and draw a two-column emoji. A glyph whose base is
Neutral therefore costs fzf one column and the terminal two, so fzf admits one
character too many onto that row. The overflow wraps, and fzf's next redraw --
which repositions with CR + cursor-forward, assuming it never left the row --
paints over the wrapped remainder, silently eating the row's last character.

Only glyphs whose base is already East Asian Wide/Fullwidth are safe; those need
no variation selector, so there is nothing for fzf to miscount.

Author: Solent Labs™
Created: 2026-08-06
"""

import re
import unicodedata
from pathlib import Path

import pytest

VARIATION_SELECTOR_16 = "️"

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
BASH_PROTOTYPE = Path(__file__).resolve().parent.parent / "bin" / "ai-launcher"

# base character immediately followed by VS16
_VS16_SEQUENCE = re.compile(rf"(.){VARIATION_SELECTOR_16}")


def _shipped_sources():
    """Every file whose text can reach a terminal."""
    files = sorted(SRC_ROOT.rglob("*.py"))
    if BASH_PROTOTYPE.exists():
        files.append(BASH_PROTOTYPE)
    return files


def _fzf_width(char: str) -> int:
    """Column count go-runewidth assigns, in fzf's default (non-East-Asian) mode."""
    if char == VARIATION_SELECTOR_16 or unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def _terminal_width(char: str, has_vs16: bool) -> int:
    """Column count a terminal draws; VS16 forces emoji presentation."""
    if has_vs16:
        return 2
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


class TestGlyphWidthAgreement:
    """No shipped glyph may be measured differently by fzf and the terminal."""

    @pytest.mark.parametrize("source", _shipped_sources(), ids=lambda p: p.name)
    def test_no_width_mismatched_vs16_sequences(self, source):
        text = source.read_text(encoding="utf-8")

        offenders = []
        for match in _VS16_SEQUENCE.finditer(text):
            base = match.group(1)
            fzf = _fzf_width(base) + _fzf_width(VARIATION_SELECTOR_16)
            terminal = _terminal_width(base, has_vs16=True)
            if fzf != terminal:
                line_no = text[: match.start()].count("\n") + 1
                offenders.append(
                    f"{source.name}:{line_no} {base}{VARIATION_SELECTOR_16} "
                    f"(U+{ord(base):04X}, EAW={unicodedata.east_asian_width(base)}) "
                    f"fzf={fzf} terminal={terminal}"
                )

        assert not offenders, (
            "Glyph(s) fzf measures narrower than the terminal draws; each one "
            "spills a column past the preview pane and eats its row's last "
            "character. Replace with an emoji whose base is East Asian Wide "
            "(U+1F300 and above) and drop the variation selector:\n  "
            + "\n  ".join(offenders)
        )


class TestReplacementGlyphsAreSafe:
    """The glyphs chosen as replacements must themselves measure identically."""

    @pytest.mark.parametrize(
        "glyph,name",
        [
            ("\U0001f527", "wrench (session configuration)"),
            ("\U0001f529", "nut and bolt (config category)"),
            ("\U0001f4d0", "triangular ruler (arch category)"),
            ("❗", "exclamation mark (warnings)"),
        ],
    )
    def test_replacement_needs_no_variation_selector(self, glyph, name):
        assert VARIATION_SELECTOR_16 not in glyph, f"{name} still carries VS16"
        assert unicodedata.east_asian_width(glyph) in ("W", "F"), (
            f"{name} (U+{ord(glyph):04X}) is not East Asian Wide, so fzf and the "
            "terminal will disagree on its width"
        )
        assert _fzf_width(glyph) == _terminal_width(glyph, has_vs16=False) == 2


class TestCategoryPrefixesStayInSync:
    """Provider category labels must still match the formatter's display order."""

    def test_provider_categories_match_formatter_prefixes(self):
        from ai_launcher.providers.claude import _categorize_global_file
        from ai_launcher.ui.formatter import PreviewFormatter

        # the prefixes the formatter matches against, pulled from its source so
        # the test breaks if the list is edited without updating the provider
        formatter_src = Path(PreviewFormatter.__module__.replace(".", "/") + ".py")
        source = (SRC_ROOT / formatter_src).read_text(encoding="utf-8")
        block = source.split("category_order = [", 1)[1].split("]", 1)[0]
        prefixes = re.findall(r'"([^"]+)",', block)

        samples = {
            "ARCHITECTURE_DECISIONS.md": "\U0001f4d0 Arch",
            "settings.json": "\U0001f529 Config",
        }
        for filename, expected_prefix in samples.items():
            assert expected_prefix in prefixes, (
                f"{expected_prefix!r} missing from formatter category_order"
            )
            label = _categorize_global_file(Path("/tmp") / filename)
            assert label.startswith(expected_prefix), (
                f"{filename} categorised as {label!r}, which does not start with "
                f"{expected_prefix!r} -- provider and formatter have drifted"
            )
