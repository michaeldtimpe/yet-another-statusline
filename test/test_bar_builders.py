import statusline_command as sl
from helper import strip_ansi


_r = sl.Renderer()



def test_gradient_bar_zero_fill_is_empty() -> None:
    assert _r.gradient_bar(0, 30) == ''


def test_gradient_bar_visible_width() -> None:
    # filled=5 → 5 FILLED glyphs (the PUA MID leading-edge glyph was removed for
    # Monaco safety, so BarChars.MID is now empty).
    result = _r.gradient_bar(5, 30)
    stripped = strip_ansi(result)
    assert sl._visible_width(stripped) == 5


def test_gradient_bar_mid_glyph_has_no_background() -> None:
    # The MID leading-edge glyph used to sit on a coloured BG to fake a pill cap.
    # The fill→empty seam is now blended by fading the leading empty chars, so
    # gradient_bar must not emit any BG SGR.
    result = _r.gradient_bar(5, 30)
    assert '\x1b[48;' not in result


def test_empty_section_fades_leading_chars() -> None:
    # First 3 empty chars ramp from a darker shade up to BAR_EMPTY; remainder
    # share BAR_EMPTY. Smaller `empty` only emits the ramp prefix.
    full = _r._empty_section(10)
    fade = _r._empty_fade_colors()
    for step in fade:
        assert step in full
    assert _r.BAR_EMPTY in full
    assert strip_ansi(full) == sl.BarChars.EMPTY * 10
    assert _r._empty_section(0) == ''
    short = strip_ansi(_r._empty_section(2))
    assert short == sl.BarChars.EMPTY * 2



def test_spec_gradient_bar_idx_wraps() -> None:
    palette_len = len(sl.Renderer.SPEC_GRADIENTS)
    result_zero = strip_ansi(_r.spec_gradient_bar(3, 30, idx=0))
    result_wrap = strip_ansi(_r.spec_gradient_bar(3, 30, idx=palette_len))
    assert result_zero == result_wrap


def test_spec_gradient_bar_content_is_heavy_glyphs() -> None:
    # After stripping ANSI, should be 3 HEAVY glyphs
    stripped = strip_ansi(_r.spec_gradient_bar(3, 30, idx=0))
    assert stripped == sl.BarChars.HEAVY * 3
