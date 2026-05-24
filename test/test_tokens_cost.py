from typing import Any

import statusline_command as sl
from helper import strip_ansi

_visible_width = sl._visible_width
Renderer = sl.Renderer

BOX_WIDTH = 160


def _call() -> Any:
    r = Renderer()
    return r.tokens_cost(
        sess_in=1, sess_cache=0, sess_out=2,
        day_in=3,  day_cache=0, day_out=4,
        sess_cost=0.01, day_cost=0.02,
        tok_rate=123, session_id='', box_width=BOX_WIDTH,
    )


def test_tokens_cost_returns_two_lines_within_box() -> None:
    lines, _cols, _mark = _call()
    assert len(lines) == 2
    for ln in lines:
        assert _visible_width(ln) <= BOX_WIDTH - 3


def test_tokens_cost_cols_within_box() -> None:
    lines, cols, _mark = _call()
    col1, col2 = cols
    assert 1 <= col1 < col2 <= BOX_WIDTH - 3


def test_tokens_cost_rate_shown_no_sparkline() -> None:
    # Flat renderer: numeric 't/m' on row 1, no sparkline, mark_col disabled.
    lines, _cols, mark_col = _call()
    text = strip_ansi('\n'.join(lines))
    assert 't/m' in text
    assert mark_col == 0
    assert not any(0x1FB00 <= ord(c) <= 0x1FBFF for c in text)  # no legacy sparkline glyphs


def test_tokens_cost_session_exact_day_estimate() -> None:
    lines, _cols, _mark = _call()
    text = strip_ansi('\n'.join(lines))
    assert '~$' in text            # day cost flagged as estimate
    assert text.count('~$') == 1   # only the day row
    assert '$0.01' in text         # session cost, no ~


def test_tokens_cost_uses_standard_arrows() -> None:
    lines, _cols, _mark = _call()
    text = strip_ansi('\n'.join(lines))
    assert '↓' in text and '↑' in text
    assert '\U0001f847' not in text and '\U0001f845' not in text  # no Supplemental-Arrows-C
