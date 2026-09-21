import json
import subprocess
import sys
from pathlib import Path

import pytest

import statusline_command as sl

_EXAMPLE = Path(__file__).resolve().parent.parent / 'claude' / 'statusline' / 'session-info-example.json'
_SCRIPT  = Path(__file__).resolve().parent.parent / 'claude' / 'statusline_command.py'


def _load_example() -> dict:
    return json.loads(_EXAMPLE.read_text())


def test_render_returns_nonempty():
    info   = _load_example()
    result = sl.render(info, 160)
    assert isinstance(result, str)
    assert len(result) > 0


def test_render_is_io_free(monkeypatch):
    class _Raise:
        def read(self, *a, **kw):   raise AssertionError('stdin touched')
        def write(self, *a, **kw):  raise AssertionError('stdout touched')
        def flush(self, *a, **kw):  raise AssertionError('stderr touched')

    monkeypatch.setattr(sys, 'stdin',  _Raise())
    monkeypatch.setattr(sys, 'stdout', _Raise())
    monkeypatch.setattr(sys, 'stderr', _Raise())

    info   = _load_example()
    result = sl.render(info, 160)
    assert len(result) > 0


def test_render_different_widths_produce_different_layouts():
    info    = _load_example()
    narrow  = sl.render(info, 50)
    wide    = sl.render(info, 160)
    assert narrow != wide


def test_render_matches_cli_subprocess(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(sl, 'HOME', tmp_path)

    info = _load_example()

    proc = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        input=json.dumps(info),
        capture_output=True,
        text=True,
        env={**os.environ, 'COLUMNS': '166', 'HOME': str(tmp_path)},
    )
    result_cli = proc.stdout

    result_api = sl.render(info, 160)

    assert result_api == result_cli.rstrip('\n')


def _tree(root: Path) -> dict:
    """Snapshot every file under root as path -> (size, mtime_ns, bytes)."""
    if not root.exists():
        return {}
    out = {}
    for p in sorted(root.rglob('*')):
        if p.is_file():
            st = p.stat()
            out[str(p)] = (st.st_size, st.st_mtime_ns, p.read_bytes())
    return out


def test_render_record_false_touches_no_state(tmp_home: Path) -> None:
    """record=False renders normally but writes nothing under HOME/.claude."""
    claude = tmp_home / '.claude'
    before = _tree(claude)

    result = sl.render(_load_example(), 160, record=False)
    assert len(result) > 0
    assert _tree(claude) == before
    assert before == {}          # and nothing was created at all


def test_render_record_true_writes_state(tmp_home: Path) -> None:
    """The default still records: the token-rate log appears."""
    result = sl.render(_load_example(), 160)
    assert len(result) > 0
    assert (tmp_home / '.claude' / 'statusline-token-rate.log').exists()


def test_render_record_false_is_repeatable(tmp_home: Path) -> None:
    """A read-only render can be repeated (mon re-renders every 2s) unchanged."""
    quiet = sl.render(_load_example(), 160, record=False)
    assert quiet == sl.render(_load_example(), 160, record=False)


@pytest.mark.parametrize('payload', ['', '   ', 'not json', '[]', '"str"', 'null'])
def test_main_ignores_bad_stdin(tmp_path, payload: str) -> None:
    """Empty, malformed or non-object stdin exits quietly, printing nothing."""
    import os
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        input=payload, capture_output=True, text=True,
        env={**os.environ, 'COLUMNS': '166', 'HOME': str(tmp_path)},
    )
    assert proc.returncode == 0
    assert proc.stdout == ''
    assert 'Traceback' not in proc.stderr
