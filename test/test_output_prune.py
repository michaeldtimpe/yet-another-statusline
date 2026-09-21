import json
import os
from pathlib import Path

import statusline_command as sl


def test_prune_output_dir_keeps_most_recent(tmp_path: Path) -> None:
    for i in range(60):
        f = tmp_path / f'statusline.{i}.json'
        f.write_text('{}')
        os.utime(f, (i, i))  # deterministic mtime ordering
    sl.prune_output_dir(tmp_path, keep=50)
    remaining = {p.name for p in tmp_path.glob('statusline.*.json')}
    assert len(remaining) == 50
    assert 'statusline.59.json' in remaining   # newest survives
    assert 'statusline.0.json' not in remaining  # oldest pruned


def test_prune_output_dir_noop_under_limit(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f'statusline.{i}.json').write_text('{}')
    sl.prune_output_dir(tmp_path, keep=50)
    assert len(list(tmp_path.glob('statusline.*.json'))) == 5


def test_prune_output_dir_missing_dir_is_safe(tmp_path: Path) -> None:
    sl.prune_output_dir(tmp_path / 'does-not-exist', keep=50)  # no raise


def test_snapshot_one_file_per_session(tmp_path: Path) -> None:
    """Two sessions rendering in the same second get one file each."""
    sl.write_payload_snapshot({'session_id': 'sess-a', 'n': 1}, tmp_path)
    sl.write_payload_snapshot({'session_id': 'sess-b', 'n': 2}, tmp_path)
    names = {p.name for p in tmp_path.glob('statusline.*.json')}
    assert names == {'statusline.sess-a.json', 'statusline.sess-b.json'}


def test_snapshot_overwrites_same_session(tmp_path: Path) -> None:
    """Re-rendering a session replaces its snapshot instead of accumulating."""
    sl.write_payload_snapshot({'session_id': 'sess-a', 'n': 1}, tmp_path)
    sl.write_payload_snapshot({'session_id': 'sess-a', 'n': 2}, tmp_path)
    files = list(tmp_path.glob('statusline.*.json'))
    assert len(files) == 1
    assert json.loads(files[0].read_text())['n'] == 2
    assert list(tmp_path.glob('*.tmp')) == []


def test_snapshot_sanitizes_session_id(tmp_path: Path) -> None:
    """A hostile session_id cannot escape out_dir."""
    out_dir = tmp_path / 'out'
    out_dir.mkdir()
    sl.write_payload_snapshot({'session_id': '../x'}, out_dir)
    assert [p.name for p in out_dir.iterdir()] == ['statusline..._x.json']
    assert list(tmp_path.glob('*.json')) == []   # nothing landed outside


def test_snapshot_skips_empty_session_id(tmp_path: Path) -> None:
    """No session_id, no file."""
    sl.write_payload_snapshot({}, tmp_path)
    sl.write_payload_snapshot({'session_id': ''}, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_snapshot_prunes_legacy_timestamp_files(tmp_path: Path) -> None:
    """The count-based prune still runs, retiring old timestamped snapshots."""
    for i in range(60):
        f = tmp_path / f'statusline.{i}.json'
        f.write_text('{}')
        os.utime(f, (i, i))
    sl.write_payload_snapshot({'session_id': 'sess-a'}, tmp_path)
    remaining = {p.name for p in tmp_path.glob('statusline.*.json')}
    assert len(remaining) == 50
    assert 'statusline.sess-a.json' in remaining
