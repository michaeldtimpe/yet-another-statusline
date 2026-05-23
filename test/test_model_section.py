import statusline_command as sl
from helper import strip_ansi

_visible_width = sl._visible_width
Renderer = sl.Renderer
RateLimits = sl.RateLimits
RateBucket = sl.RateBucket
SessionInfo = sl.SessionInfo
Model = sl.Model
Thinking = sl.Thinking
Effort = sl.Effort


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


# Single-row guarantee: fit_path + model section always co-exist on row 1

class TestSingleRowGuarantee:
    _vsep_w = 5

    def _wide_combo(self, r: Renderer, width: int) -> tuple[str, str, str, int]:
        git    = sl.GitInfo(branch='feat/long', commit='abc1234', modified=3, untracked=2)
        helper, right, right_w = r.model_right_section(
            'Sonnet 4.6', '', RateLimits()
        )
        helper_w = _visible_width(helper)
        target_w = (width - 4) - self._vsep_w - helper_w - right_w
        path = r.fit_path('~/deep/project/submodule/src', git, '15m', target_w,
                          compact_only=False)
        return path, helper, right, right_w

    def _medium_combo(self, r: Renderer, width: int) -> tuple[str, str, str, int]:
        git    = sl.GitInfo(branch='feat/long', commit='abc1234', modified=3)
        _rate, right, right_w = r.model_right_section_compact(
            'Sonnet 4.6', RateLimits(), max_right_width=max(8, width // 2),
        )
        rate_w   = _visible_width(_rate)
        target_w = (width - 4) - self._vsep_w - rate_w - right_w
        path = r.fit_path('~/deep/project/submodule/src', git, '', target_w,
                          compact_only=True)
        return path, _rate, right, right_w

    def test_wide_path_fits_target_at_borderline(self) -> None:
        r = Renderer()
        for width in (sl.MEDIUM_WIDTH, 100, sl.MAX_WIDTH):
            git    = sl.GitInfo(branch='feat/long', commit='abc1234', modified=3, untracked=2)
            helper, _right, right_w = r.model_right_section('Sonnet 4.6', '', RateLimits())
            helper_w = _visible_width(helper)
            target_w = (width - 4) - self._vsep_w - helper_w - right_w
            path = r.fit_path('~/deep/project/submodule/src', git, '15m', target_w)
            assert _visible_width(path) <= target_w, f'width={width}: path overflows target_w={target_w}'

    def test_medium_path_fits_target_at_borderline(self) -> None:
        r = Renderer()
        for width in (sl.NARROW_WIDTH, 68, sl.MEDIUM_WIDTH - 1):
            git    = sl.GitInfo(branch='feat/long', commit='abc1234', modified=3)
            _rate, _right, right_w = r.model_right_section_compact(
                'Sonnet 4.6', RateLimits(), max_right_width=max(8, width // 2),
            )
            rate_w   = _visible_width(_rate)
            target_w = (width - 4) - self._vsep_w - rate_w - right_w
            path = r.fit_path('~/deep/project/submodule/src', git, '', target_w,
                              compact_only=True)
            assert _visible_width(path) <= target_w, f'width={width}: path overflows target_w={target_w}'

    def test_wide_model_on_right_of_content_row(self) -> None:
        r = Renderer()
        width = 90
        path, helper, right, right_w = self._wide_combo(r, width)
        path_w   = _visible_width(path)
        helper_w = _visible_width(helper)
        row_text = path + helper + right
        total    = path_w + self._vsep_w + helper_w + right_w
        assert total <= width - 4, f'row overflows: total={total} width={width}'
        assert strip_ansi(right_w and right or right) != ''

    def test_medium_model_on_right_of_content_row(self) -> None:
        r = Renderer()
        width = 70
        path, rate, right, right_w = self._medium_combo(r, width)
        path_w = _visible_width(path)
        rate_w = _visible_width(rate)
        total  = path_w + self._vsep_w + rate_w + right_w
        assert total <= width - 4, f'row overflows: total={total} width={width}'


# Narrow layout: pill on the right

def _narrow_session(model_name: str = 'Sonnet 4.6', effort_level: str = '', thinking: bool = False) -> SessionInfo:
    return SessionInfo(
        model    = Model(id='claude-sonnet-4-6', display_name=model_name),
        effort   = Effort(level=effort_level),
        thinking = Thinking(enabled=thinking),
    )


class TestNarrowPillOnRight:
    def test_pill_placed_at_right_edge_when_thinking_active(self) -> None:
        r = Renderer()
        width = 50
        session = _narrow_session('Opus 4.7', effort_level='high', thinking=True)
        spec = sl.build_narrow(session, width, r)
        pill = next(row.pill for row in spec.rows if row.pill is not None)
        assert pill.end == width, 'pill must end at right edge'
        assert pill.start > 1,   'pill must not start at left edge'

    def test_content_row_uses_right_pill_when_thinking_active(self) -> None:
        r = Renderer()
        session = _narrow_session('Opus 4.7', effort_level='high', thinking=True)
        spec = sl.build_narrow(session, 50, r)
        content_rows = [row for row in spec.rows if row.kind == 'content']
        model_row = content_rows[0]
        assert model_row.right_pill != '', 'model row must use right_pill when pill active'
        assert not model_row.pill_flush,   'pill_flush must be False when right_pill is used'

    def test_no_pill_when_thinking_disabled(self) -> None:
        r = Renderer()
        session = _narrow_session('Sonnet 4.6', thinking=False)
        spec = sl.build_narrow(session, 50, r)
        assert all(row.pill is None for row in spec.rows), 'no pill when thinking disabled'

    def test_rendered_top_border_starts_with_normal_corner(self) -> None:
        r = Renderer()
        session = _narrow_session('Opus 4.7', effort_level='high', thinking=True)
        spec = sl.build_narrow(session, 50, r)
        lines = sl.render_layout(spec, r)
        top = strip_ansi(lines[0])
        assert top.startswith('╭'), 'top-left corner must be ╭ when pill is on right'

    def test_rendered_separator_ends_with_pill_bottom(self) -> None:
        r = Renderer()
        session = _narrow_session('Opus 4.7', effort_level='high', thinking=True)
        spec = sl.build_narrow(session, 50, r)
        lines = sl.render_layout(spec, r)
        sep = strip_ansi(lines[2])
        assert sep.endswith(sl.PILL_BR), 'separator must end with PILL_BR when pill is on right'
