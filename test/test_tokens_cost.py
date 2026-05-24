from typing import Any

import pytest

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
        tok_rate=0, session_id='', box_width=BOX_WIDTH,
    )


def test_tokens_cost_returns_two_equal_width_lines() -> None:
    lines, cols, _mark_col = _call()
    assert len(lines) == 2
    assert _visible_width(lines[0]) == _visible_width(lines[1])


def test_tokens_cost_cols_within_box() -> None:
    lines, cols, _mark_col = _call()
    col1, col2 = cols
    assert 1 <= col1
    assert col1 < col2
    assert col2 <= BOX_WIDTH - 3


def test_tokens_cost_row1_starts_with_rate_icon_in_right_section() -> None:
    lines, cols, _mark_col = _call()
    _, col2 = cols
    row1_stripped = strip_ansi(lines[0])
    leader_start = col2 - 1
    assert row1_stripped[leader_start] == sl.ICON_TOK_RATE


def test_tokens_cost_row2_right_section_begins_with_15_spaces() -> None:
    lines, cols, _mark_col = _call()
    _, col2 = cols
    row2_stripped = strip_ansi(lines[1])
    leader_start = col2 - 1
    assert row2_stripped[leader_start:leader_start + 15] == ' ' * 15


def test_tokens_cost_day_cost_marked_estimate() -> None:
    # Day cost is a rate-card estimate and must be flagged with a leading ~,
    # while the session cost (authoritative) is not.
    lines, _cols, _mark = _call()
    text = strip_ansi('\n'.join(lines))
    assert '~$' in text          # day cost estimate marker
    assert text.count('~$') == 1  # only the day row, not the session row


def test_tokens_cost_active_arrows_use_font_safe_glyphs(monkeypatch: pytest.MonkeyPatch) -> None:
    # While token I/O is flowing the row uses Nerd Font heavy arrows
    # (md-arrow_down_bold / md-arrow_up_bold) that real monospace fonts ship.
    # The old 🡇/🡅 (Supplemental Arrows-C) are absent from every common font
    # and rendered as tofu whenever the row refreshed during active flow.
    monkeypatch.setattr(sl.TokenRate, 'recently_active',
                        staticmethod(lambda *a, **k: (True, True)))
    r = Renderer()
    lines, _cols, _mark = r.tokens_cost(
        sess_in=1, sess_cache=0, sess_out=2,
        day_in=3,  day_cache=0, day_out=4,
        sess_cost=0.01, day_cost=0.02,
        tok_rate=0, session_id='s', box_width=BOX_WIDTH,
    )
    text = '\n'.join(lines)
    assert sl.GLYPH_TOK_IN_ACTIVE in text
    assert sl.GLYPH_TOK_OUT_ACTIVE in text
    assert '\U0001f847' not in text and '\U0001f845' not in text
    # The replacement glyphs must stay single-column so the box stays aligned.
    assert _visible_width(lines[0]) == _visible_width(lines[1])


def test_tokens_cost_spark_mark_col_lies_inside_sparkline() -> None:
    # The mark col is the 60s tick that build_wide threads into the separator
    # above the tokens rows. It must sit strictly between the vsep_leader │
    # (col2) and the right-hand box border.
    lines, cols, mark_col = _call()
    _, col2 = cols
    assert col2 < mark_col < BOX_WIDTH
