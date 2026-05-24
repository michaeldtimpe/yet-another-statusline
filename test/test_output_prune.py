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
