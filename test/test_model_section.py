import statusline_command as sl
from conftest import strip_ansi

_visible_width = sl._visible_width
Renderer = sl.Renderer
RateLimits = sl.RateLimits
RateBucket = sl.RateBucket


def test_model_right_section_no_seven_day_suffix() -> None:
    r = Renderer()
    helper, _right, _w = r.model_right_section('Sonnet 4.6', '', RateLimits())
    assert '%' not in strip_ansi(helper)


def test_model_right_section_seven_day_appears_when_used() -> None:
    r = Renderer()
    rate = RateLimits(seven_day=RateBucket(used_percentage=12.5))
    helper, _right, _w = r.model_right_section('Sonnet 4.6', '', rate)
    assert '12.5%' in strip_ansi(helper)


def test_model_right_section_pill_inactive_plain_text() -> None:
    r = Renderer()
    _helper, right, w = r.model_right_section('Sonnet 4.6', '', RateLimits())
    stripped = strip_ansi(right)
    assert 'Sonnet 4.6' in stripped
    assert sl.PILL_LEFT not in stripped
    assert sl.PILL_RIGHT not in stripped
    assert w == _visible_width(right)


def test_model_right_section_pill_active_wraps_with_caps() -> None:
    r = Renderer()
    _helper, right, w = r.model_right_section('Opus 4.7 1M', 'high', RateLimits(), effort_level='high')
    stripped = strip_ansi(right)
    assert stripped.startswith(sl.PILL_LEFT)
    assert stripped.endswith(sl.PILL_RIGHT)
    assert 'Opus 4.7 1M' in stripped
    assert 'high' in stripped
    assert w == _visible_width(right)


def test_model_right_section_compact_respects_max_width() -> None:
    r = Renderer()
    _rate, right, w = r.model_right_section_compact('A' * 100, RateLimits(), max_right_width=20)
    assert w <= 20
    assert '…' in strip_ansi(right)


def test_model_section_compact_respects_max_width() -> None:
    r = Renderer()
    out, _ = r.model_section_compact('A' * 100, RateLimits(), max_width=30)
    assert _visible_width(out) <= 30
    assert '…' in strip_ansi(out)
