"""Tests for terminal_width()'s tmux detector and _osascript_width()'s
TERM_PROGRAM-gated fallback (no launching iTerm2, no unbounded osascript spawn
on every render)."""
import subprocess
from pathlib import Path
from typing import Any

import pytest

import statusline_command as sl


class FakeCompleted:
    def __init__(self, stdout: str = '') -> None:
        self.stdout = stdout
        self.stderr = ''


class RecordingRun:
    """Stand-in for subprocess.run that records calls and returns a fixed
    result (or raises), so tests can assert on both invocation and args."""

    def __init__(self, result: Any = None, exc: BaseException | None = None) -> None:
        self.result = result if result is not None else FakeCompleted('')
        self.exc = exc
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> Any:
        self.calls.append(cmd)
        if self.exc is not None:
            raise self.exc
        return self.result


class TestTerminalWidthTmux:
    def test_tmux_not_queried_when_unset(self, monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
        monkeypatch.delenv('TMUX', raising=False)
        monkeypatch.delenv('TMUX_PANE', raising=False)
        monkeypatch.setenv('COLUMNS', '100')  # short-circuits before osascript
        run = RecordingRun()
        monkeypatch.setattr(sl.subprocess, 'run', run)
        assert sl.terminal_width() == 100
        assert run.calls == []

    def test_tmux_queried_with_target_pane(self, monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
        monkeypatch.setenv('TMUX', '/tmp/tmux-1000/default,1234,0')
        monkeypatch.setenv('TMUX_PANE', '%7')
        run = RecordingRun(FakeCompleted('123'))
        monkeypatch.setattr(sl.subprocess, 'run', run)
        assert sl.terminal_width() == 123
        assert len(run.calls) == 1
        cmd = run.calls[0]
        assert cmd[0] == 'tmux'
        assert '-t' in cmd
        assert cmd[cmd.index('-t') + 1] == '%7'

    def test_tmux_timeout_falls_through(self, monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
        monkeypatch.setenv('TMUX', '/tmp/tmux-1000/default,1234,0')
        monkeypatch.delenv('TMUX_PANE', raising=False)
        monkeypatch.setenv('COLUMNS', '77')
        run = RecordingRun(exc=subprocess.TimeoutExpired(cmd=['tmux'], timeout=1))
        monkeypatch.setattr(sl.subprocess, 'run', run)
        # Must not raise — falls through to the next detector (COLUMNS).
        assert sl.terminal_width() == 77


class TestOsascriptWidth:
    def _cache(self, tmp_home: Path) -> Path:
        return tmp_home / '.claude' / '.statusline-width'

    def test_unrecognized_term_program_never_spawns_osascript(
        self, monkeypatch: pytest.MonkeyPatch, tmp_home: Path
    ) -> None:
        monkeypatch.setattr(sl.sys, 'platform', 'darwin')
        monkeypatch.setenv('TERM_PROGRAM', 'tmux')
        run = RecordingRun()
        monkeypatch.setattr(sl.subprocess, 'run', run)
        assert sl._osascript_width() == 0
        assert run.calls == []

    def test_apple_terminal_runs_one_script_mentioning_terminal(
        self, monkeypatch: pytest.MonkeyPatch, tmp_home: Path
    ) -> None:
        monkeypatch.setattr(sl.sys, 'platform', 'darwin')
        monkeypatch.setenv('TERM_PROGRAM', 'Apple_Terminal')
        run = RecordingRun(FakeCompleted('90'))
        monkeypatch.setattr(sl.subprocess, 'run', run)
        assert sl._osascript_width() == 90
        assert len(run.calls) == 1
        script = run.calls[0][run.calls[0].index('-e') + 1]
        assert 'Terminal' in script
        assert 'iTerm2' not in script

    def test_failure_is_cached_so_second_call_spawns_nothing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_home: Path
    ) -> None:
        monkeypatch.setattr(sl.sys, 'platform', 'darwin')
        monkeypatch.setenv('TERM_PROGRAM', 'Apple_Terminal')
        run = RecordingRun(FakeCompleted('not-a-number'))
        monkeypatch.setattr(sl.subprocess, 'run', run)
        assert sl._osascript_width() == 0
        assert len(run.calls) == 1
        assert self._cache(tmp_home).exists()

        # Second call within the 5s freshness window must not spawn osascript.
        run2 = RecordingRun()
        monkeypatch.setattr(sl.subprocess, 'run', run2)
        assert sl._osascript_width() == 0
        assert run2.calls == []
