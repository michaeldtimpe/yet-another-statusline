"""Tests for TokenRate.update (disk I/O parsers)."""
from pathlib import Path

import pytest

import statusline_command as sl


NOW = 1_000_000.0  # fixed "now" for all tests


class FakeTime:
    """Minimal time namespace stub with a settable .time() function."""
    _now = NOW

    @staticmethod
    def time() -> float:
        return FakeTime._now


def _log_path(tmp_home: Path) -> Path:
    return tmp_home / '.claude' / 'statusline-token-rate.log'


def _write_row(path: Path, ts: float, session_id: str, total_in: int, total_out: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as fh:
        fh.write(f'{ts:.3f} {session_id} {total_in} {total_out}\n')


def setup_rate(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> Path:
    """Patch time and constants to deterministic values; return log path."""
    monkeypatch.setattr(sl, 'time', FakeTime)
    monkeypatch.setattr(sl.TokenRate, 'WINDOW', 60.0)
    monkeypatch.setattr(sl.TokenRate, 'KEEP', 300.0)
    return _log_path(tmp_home)


def test_single_sample_returns_zero(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
    """Empty log + first update returns 0."""
    setup_rate(monkeypatch, tmp_home)
    result = sl.TokenRate.update('sess-1', 100, 200)
    assert result == 0


def test_two_samples_in_window_return_delta(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
    """One synthetic row 30 s ago + new update returns the token delta."""
    log = setup_rate(monkeypatch, tmp_home)
    _write_row(log, NOW - 30, 'sess-1', 100, 200)

    result = sl.TokenRate.update('sess-1', 150, 250)
    # delta = (150 + 250) - (100 + 200) = 100
    assert result == 100


def test_stale_rows_pruned_from_disk(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
    """Rows older than KEEP are removed from disk."""
    log = setup_rate(monkeypatch, tmp_home)
    _write_row(log, NOW - 9999, 'sess-1', 1, 1)

    sl.TokenRate.update('sess-1', 0, 0)

    content = log.read_text()
    assert f'{NOW - 9999:.3f}' not in content


def test_update_record_false_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
    """record=False computes the rate from the log on disk and never writes."""
    log = setup_rate(monkeypatch, tmp_home)
    FakeTime._now = NOW
    _write_row(log, NOW - 30.0, 'sess-1', 100, 50)
    _write_row(log, NOW - 10.0, 'sess-1', 300, 150)
    before = log.read_text()

    rate = sl.TokenRate.update('sess-1', 999_999, 999_999, record=False)
    assert rate == 300          # (300+150) - (100+50); the live counts are ignored
    assert log.read_text() == before


def test_update_record_false_on_missing_log_is_noop(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
    """record=False never creates the log file."""
    log = setup_rate(monkeypatch, tmp_home)
    assert sl.TokenRate.update('sess-1', 100, 50, record=False) == 0
    assert not log.exists()


def test_update_record_true_still_appends(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
    """The default still records a sample."""
    log = setup_rate(monkeypatch, tmp_home)
    FakeTime._now = NOW
    sl.TokenRate.update('sess-1', 100, 50)
    assert log.read_text().splitlines() == [f'{NOW:.3f} sess-1 100 50']


@pytest.mark.parametrize('raw', ['', 'abc', '0', '-5', 'nan '])
def test_env_seconds_falls_back(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    """A malformed or non-positive window falls back instead of raising."""
    monkeypatch.setenv('STATUSLINE_TOKEN_WINDOW', raw)
    assert sl._env_seconds('STATUSLINE_TOKEN_WINDOW', 60.0) == 60.0


def test_env_seconds_accepts_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('STATUSLINE_TOKEN_WINDOW', '30')
    assert sl._env_seconds('STATUSLINE_TOKEN_WINDOW', 60.0) == 30.0


def test_env_seconds_unset_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('STATUSLINE_TOKEN_WINDOW', raising=False)
    assert sl._env_seconds('STATUSLINE_TOKEN_WINDOW', 60.0) == 60.0


def test_update_unreadable_log_returns_zero(monkeypatch: pytest.MonkeyPatch, tmp_home: Path) -> None:
    """An unreadable log (e.g. a directory sitting at the log path) must not raise."""
    log = setup_rate(monkeypatch, tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.mkdir()  # log.read_text() raises IsADirectoryError (an OSError) here
    assert sl.TokenRate.update('sess-1', 100, 50, record=False) == 0
