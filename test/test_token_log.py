"""Tests for TokenLog.update (disk I/O parser)."""
from pathlib import Path

import statusline_command as sl


TODAY = '2026-05-19'
YESTERDAY = '2026-05-18'


def _log_path(tmp_home: Path) -> Path:
    return tmp_home / '.claude' / 'statusline-tokens.log'


def test_empty_log_first_write(tmp_home: Path) -> None:
    """Empty log + first write produces one row and the expected TokenLog."""
    result = sl.TokenLog.update('sess-1', TODAY, 100, 50, 200)
    assert result == sl.TokenLog(day_in=100, day_cache_read=50, day_out=200)
    lines = _log_path(tmp_home).read_text().splitlines()
    assert lines == [f'{TODAY} sess-1 100 50 200']


def test_replace_same_session(tmp_home: Path) -> None:
    """Replacing the same session_id rewrites that row only."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(f'{TODAY} sess-1 100 50 200\n')

    result = sl.TokenLog.update('sess-1', TODAY, 150, 60, 250)
    assert result == sl.TokenLog(day_in=150, day_cache_read=60, day_out=250)
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    assert lines[0] == f'{TODAY} sess-1 150 60 250'


def test_rollup_multiple_sessions(tmp_home: Path) -> None:
    """Rollup across multiple sessions on the same day."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(f'{TODAY} sess-1 100 50 200\n')

    result = sl.TokenLog.update('sess-2', TODAY, 50, 25, 100)
    assert result == sl.TokenLog(day_in=150, day_cache_read=75, day_out=300)
    lines = log.read_text().splitlines()
    assert len(lines) == 2


def test_legacy_4_column_rows(tmp_home: Path) -> None:
    """Legacy 4-column rows (no cache column) are tolerated."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    # 4-column: date session_id in out (no cache)
    log.write_text(f'{TODAY} sess-x 100 200\n')

    # Call with zeros so no new row is added for the session
    result = sl.TokenLog.update('sess-1', TODAY, 0, 0, 0)
    # legacy row: day_in=100, day_cache_read=0, day_out=200
    assert result == sl.TokenLog(day_in=100, day_cache_read=0, day_out=200)


def test_other_days_excluded_from_return_preserved_on_disk(tmp_home: Path) -> None:
    """Rows from other days are excluded from the return value but preserved on disk."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(f'{YESTERDAY} old 99 9 99\n')

    result = sl.TokenLog.update('sess-1', TODAY, 10, 1, 20)
    assert result == sl.TokenLog(day_in=10, day_cache_read=1, day_out=20)

    content = log.read_text()
    assert YESTERDAY in content  # yesterday's row preserved
    assert 'old' in content


OLD = '2026-05-01'        # 18 days before TODAY
WEEK_AGO = '2026-05-12'   # exactly KEEP_DAYS before TODAY


def test_old_rows_pruned_on_rewrite(tmp_home: Path) -> None:
    """Rows older than KEEP_DAYS are dropped when the log is rewritten."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        f'{OLD} ancient 99 9 99\n'
        f'{WEEK_AGO} weekold 1 1 1\n'
        f'{YESTERDAY} recent 5 5 5\n'
    )

    sl.TokenLog.update('sess-1', TODAY, 10, 1, 20)

    content = log.read_text()
    assert 'ancient' not in content       # beyond the 7-day window
    assert 'weekold' in content           # exactly KEEP_DAYS old: kept
    assert 'recent' in content
    assert 'sess-1' in content


def test_undated_junk_rows_pruned(tmp_home: Path) -> None:
    """Rows whose date field doesn't parse are junk and are dropped."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(f'garbage sess-junk 1 2 3\n\n{TODAY} keeper 1 1 1\n')

    sl.TokenLog.update('sess-1', TODAY, 10, 1, 20)

    lines = log.read_text().splitlines()
    assert 'garbage sess-junk 1 2 3' not in lines
    assert f'{TODAY} keeper 1 1 1' in lines


def test_prune_keeps_today_rows_from_other_sessions(tmp_home: Path) -> None:
    """Today's rows from other sessions survive and still roll up."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(f'{OLD} ancient 1000 1000 1000\n{TODAY} sess-2 100 50 200\n')

    result = sl.TokenLog.update('sess-1', TODAY, 10, 1, 20)

    # day totals see both of today's sessions and nothing from the pruned row
    assert result == sl.TokenLog(day_in=110, day_cache_read=51, day_out=220)
    assert 'ancient' not in log.read_text()


def test_unwritable_log_degrades_quietly(monkeypatch, tmp_home: Path) -> None:
    """A failing write still returns the rolled-up totals instead of raising."""
    def boom(path, text):
        raise OSError('read-only')
    monkeypatch.setattr(sl, '_atomic_write', boom)

    result = sl.TokenLog.update('sess-1', TODAY, 10, 1, 20)
    assert result == sl.TokenLog(day_in=10, day_cache_read=1, day_out=20)


def test_unreadable_log_degrades_quietly(tmp_home: Path) -> None:
    """An unreadable log reads as 'no log' rather than crashing the statusline."""
    log = _log_path(tmp_home)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.mkdir()   # a directory where a file is expected: read_text raises OSError

    result = sl.TokenLog.update('sess-1', TODAY, 10, 1, 20)
    assert result == sl.TokenLog(day_in=10, day_cache_read=1, day_out=20)
