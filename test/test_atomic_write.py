"""Tests for the _atomic_write state-file helper."""
from pathlib import Path

import pytest

import statusline_command as sl


def _temps(d: Path) -> list[Path]:
    return sorted(d.glob('*.tmp'))


def test_atomic_write_creates_parents(tmp_path: Path) -> None:
    """Missing parent directories are created."""
    target = tmp_path / 'a' / 'b' / 'state.log'
    sl._atomic_write(target, 'hello\n')
    assert target.read_text() == 'hello\n'
    assert _temps(target.parent) == []


def test_atomic_write_replaces_content(tmp_path: Path) -> None:
    """A second write replaces the file and leaves no temp behind."""
    target = tmp_path / 'state.log'
    target.write_text('old content that is much longer\n')
    sl._atomic_write(target, 'new\n')
    assert target.read_text() == 'new\n'
    assert _temps(tmp_path) == []
    assert [p.name for p in tmp_path.iterdir()] == ['state.log']


def test_atomic_write_unwritable_dir_raises_and_cleans_up(tmp_path: Path) -> None:
    """A write into a read-only directory raises OSError, leaving no temp."""
    d = tmp_path / 'ro'
    d.mkdir()
    d.chmod(0o555)
    try:
        with pytest.raises(OSError):
            sl._atomic_write(d / 'state.log', 'x\n')
        assert _temps(d) == []
    finally:
        d.chmod(0o755)


def test_atomic_write_parent_is_a_file_raises(tmp_path: Path) -> None:
    """A parent that cannot be created (it is a file) raises OSError."""
    blocker = tmp_path / 'blocker'
    blocker.write_text('not a directory\n')
    with pytest.raises(OSError):
        sl._atomic_write(blocker / 'state.log', 'x\n')
    assert blocker.read_text() == 'not a directory\n'
    assert _temps(tmp_path) == []
