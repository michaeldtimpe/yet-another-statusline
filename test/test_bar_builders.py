import statusline_command as sl
from conftest import strip_ansi


_r = sl.Renderer()


# ---------------------------------------------------------------------------
# 7.2  gradient_bar
# ---------------------------------------------------------------------------

def test_gradient_bar_zero_fill_is_empty() -> None:
    assert _r.gradient_bar(0, 30) == ''


def test_gradient_bar_visible_width() -> None:
    # filled=5 → 5 FILLED glyphs + 1 MID leading-edge glyph = 6 visible chars
    result = _r.gradient_bar(5, 30)
    stripped = strip_ansi(result)
    assert sl._visible_width(stripped) == 6


def test_gradient_bar_mid_bg_lands_before_mid_glyph() -> None:
    # mid_bg ANSI (e.g. converted from BAR_EMPTY fg) must precede the MID
    # leading-edge glyph so the semi-circle sits on the empty-bar grey.
    mid_bg = sl._fg_to_bg(_r.BAR_EMPTY)
    result = _r.gradient_bar(5, 30, mid_bg)
    mid_idx = result.rfind(sl.BarChars.MID)
    assert mid_idx > 0
    assert mid_bg in result[:mid_idx]


def test_fg_to_bg_converts_256_and_truecolor() -> None:
    assert sl._fg_to_bg('\x1b[38;5;238m')         == '\x1b[48;5;238m'
    assert sl._fg_to_bg('\x1b[38;2;188;192;204m') == '\x1b[48;2;188;192;204m'
    assert sl._fg_to_bg('\x1b[1m')                == '\x1b[1m'


# ---------------------------------------------------------------------------
# 7.3  spec_gradient_bar: idx wraps modulo palette length
# ---------------------------------------------------------------------------

def test_spec_gradient_bar_idx_wraps() -> None:
    palette_len = len(sl.Renderer.SPEC_GRADIENTS)
    result_zero = strip_ansi(_r.spec_gradient_bar(3, 30, idx=0))
    result_wrap = strip_ansi(_r.spec_gradient_bar(3, 30, idx=palette_len))
    assert result_zero == result_wrap


def test_spec_gradient_bar_content_is_heavy_glyphs() -> None:
    # After stripping ANSI, should be 3 HEAVY glyphs
    stripped = strip_ansi(_r.spec_gradient_bar(3, 30, idx=0))
    assert stripped == sl.BarChars.HEAVY * 3
