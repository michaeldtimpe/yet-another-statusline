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
    assert '~' not in out and '↑' not in out and '↓' not in out


def test_git_behind_shows_drift(monkeypatch, tmp_path) -> None:
    g = sl.GitInfo(branch='main', commit='abc1234', behind=2, has_upstream=True)
    out = _render(monkeypatch, tmp_path, g)
    assert '↓2' in out
    assert '✓' not in out


def test_full_home_relative_path_shown(monkeypatch, tmp_path) -> None:
    g = sl.GitInfo()  # no branch -> no git segment
    home = os.path.expanduser('~')
    out = _render(monkeypatch, tmp_path, g, cwd=f'{home}/Downloads/yet-another-statusline')
    assert '~/Downloads/yet-another-statusline' in out


def test_path_truncates_when_narrow_keeping_model(monkeypatch, tmp_path) -> None:
    g = sl.GitInfo(branch='main', commit='abc1234')
    home = os.path.expanduser('~')
    out = _render(monkeypatch, tmp_path, g,
                  cwd=f'{home}/very/deep/nested/project/path/that/is/long', width=70)
    assert '…' in out                       # path was truncated
    assert out.rstrip().endswith('Opus')    # model stayed pinned last
