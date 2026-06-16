import os
import re

import statusline_command as sl
from helper import strip_ansi

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def _render(monkeypatch, tmp_path, git, width=240, cwd=None):
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl.GitInfo, 'from_cwd', staticmethod(lambda c: git))
    info = {
        'session_id': 's', 'cwd': cwd or str(tmp_path),
        'model': {'id': 'opus', 'display_name': 'Opus'},
        'context_window': {'total_input_tokens': 1, 'total_output_tokens': 1,
                           'context_window_size': 200000},
    }
    return strip_ansi(sl.render(info, width))


def test_git_markers_and_pending_state(monkeypatch, tmp_path) -> None:
    g = sl.GitInfo(branch='main', commit='abc1234', modified=2, untracked=1,
                   ahead=3, has_upstream=True)
    out = _render(monkeypatch, tmp_path, g)
    assert 'git main/abc1234' in out
    assert '+1' in out and '~2' in out and '↑3' in out  # untracked / modified / ahead
    assert '✓' not in out


def test_git_clean_synced_shows_check(monkeypatch, tmp_path) -> None:
    g = sl.GitInfo(branch='main', commit='abc1234', has_upstream=True)
    out = _render(monkeypatch, tmp_path, g)
    assert '✓' in out
    # No dirty/drift markers. (A bare `~` now legitimately appears as the
    # home-relative path prefix, so check the modified marker `~<count>`.)
    assert not re.search(r'~\d', out) and '↑' not in out and '↓' not in out


def test_git_behind_shows_drift(monkeypatch, tmp_path) -> None:
    g = sl.GitInfo(branch='main', commit='abc1234', behind=2, has_upstream=True)
    out = _render(monkeypatch, tmp_path, g)
    assert '↓2' in out
    assert '✓' not in out


def test_minimized_home_relative_path_shown(monkeypatch, tmp_path) -> None:
    # Path is always minimized: intermediate dirs collapse to their first
    # letter, the project name stays full. HOME is the monkeypatched tmp_path.
    g = sl.GitInfo()  # no branch -> no git segment
    out = _render(monkeypatch, tmp_path, g, cwd=f'{tmp_path}/Downloads/yet-another-statusline')
    assert '~/D/yet-another-statusline' in out
    assert '~/Downloads/yet-another-statusline' not in out


def test_path_truncates_when_narrow_keeping_model(monkeypatch, tmp_path) -> None:
    g = sl.GitInfo(branch='main', commit='abc1234')
    home = os.path.expanduser('~')
    out = _render(monkeypatch, tmp_path, g,
                  cwd=f'{home}/very/deep/nested/project/path/that/is/long', width=70)
    assert '…' in out                       # path was truncated
    assert out.rstrip().endswith('Opus')    # model stayed pinned last


def _render_info(monkeypatch, tmp_path, info, width=240):
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl.GitInfo, 'from_cwd', staticmethod(lambda c: sl.GitInfo()))
    base = {
        'session_id': 's', 'cwd': str(tmp_path),
        'model': {'id': 'opus', 'display_name': 'Opus'},
        'context_window': {'total_input_tokens': 1, 'total_output_tokens': 1,
                           'context_window_size': 200000},
    }
    base.update(info)
    return strip_ansi(sl.render(base, width))


def test_subscription_plan_shows_limits_and_plan_tag(monkeypatch, tmp_path) -> None:
    out = _render_info(monkeypatch, tmp_path, {
        'rate_limits': {'five_hour': {'used_percentage': 61, 'resets_at': 0},
                        'seven_day': {'used_percentage': 89, 'resets_at': 0}},
    })
    assert '5h 61%' in out and '7d 89%' in out
    assert 'plan' in out
    assert 'api' not in out and 'est' not in out


def test_api_billing_replaces_limits_with_estimated_cost(monkeypatch, tmp_path) -> None:
    # No rate_limits -> API billing. The 5h/7d windows are replaced by an
    # estimated session cost and tagged `api`.
    out = _render_info(monkeypatch, tmp_path, {'cost': {'total_cost_usd': 1.23}})
    assert 'api' in out
    assert 'est $1.23' in out
    assert 'plan' not in out and '5h ' not in out and '7d ' not in out
