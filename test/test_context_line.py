import statusline_command as sl
from helper import strip_ansi

_visible_width = sl._visible_width
Renderer = sl.Renderer
ContextWindow = sl.ContextWindow
CLR_ALERT = sl.CLR_ALERT
SOFT_LIMIT = sl.SOFT_LIMIT


def test_context_line_under_soft_limit() -> None:
    r = Renderer()
    ctx = ContextWindow(
        total_input_tokens=10_000,
        total_output_tokens=5_000,
        context_window_size=200_000,
    )
    available = 76
    out = r.context_line(ctx, available)
    assert _visible_width(out) <= available
    assert CLR_ALERT not in out


def test_context_line_over_soft_limit() -> None:
    r = Renderer()
    ctx = ContextWindow(
        total_input_tokens=200_000,
        total_output_tokens=0,
        context_window_size=200_000,
    )
    available = 76
    out = r.context_line(ctx, available)
    assert CLR_ALERT in out
    assert _visible_width(out) <= available


def test_context_line_caps_compaction_pct_at_100() -> None:
    # 280K / 150K soft limit = 187% raw; the displayed compaction % must cap at
    # 100% (the window-fill secondary "(28%)" is separate and unaffected).
    r = Renderer()
    ctx = ContextWindow(
        total_input_tokens=280_000,
        total_output_tokens=0,
        context_window_size=1_000_000,
    )
    plain = strip_ansi(r.context_line(ctx, 120))
    assert '100%' in plain
    assert '187%' not in plain
    assert '(28%)' in plain  # window-fill secondary still shown


def test_context_line_compact_respects_available() -> None:
    r = Renderer()
    ctx = ContextWindow(
        total_input_tokens=10_000,
        total_output_tokens=5_000,
    )
    available = 30
    out = r.context_line_compact(ctx, available)
    assert _visible_width(out) <= available
