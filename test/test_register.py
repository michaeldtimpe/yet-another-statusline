import importlib.util
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / 'claude' / 'register_statusline.py'
_spec = importlib.util.spec_from_file_location('register_statusline', _SRC)
reg = importlib.util.module_from_spec(_spec)
sys.modules['register_statusline'] = reg
_spec.loader.exec_module(reg)


def test_register_merges_without_clobber(tmp_path, monkeypatch) -> None:
    p = tmp_path / 'settings.json'
    p.write_text(json.dumps({'model': 'opus[1m]', 'permissions': {'allow': ['x']}}))
    monkeypatch.setattr(reg, 'SETTINGS', str(p))
    assert reg.main() == 0
    d = json.loads(p.read_text())
    assert d['model'] == 'opus[1m]'                 # preserved
    assert d['permissions'] == {'allow': ['x']}     # preserved
    assert d['statusLine']['command'] == 'python3 ~/.claude/statusline_command.py'


def test_register_creates_and_is_idempotent(tmp_path, monkeypatch, capsys) -> None:
    p = tmp_path / 'settings.json'
    monkeypatch.setattr(reg, 'SETTINGS', str(p))
    assert reg.main() == 0                            # creates file
    assert json.loads(p.read_text())['statusLine']['type'] == 'command'
    assert reg.main() == 0                            # second run is a no-op
    assert 'already registered' in capsys.readouterr().out


def test_register_leaves_malformed_json_untouched(tmp_path, monkeypatch) -> None:
    p = tmp_path / 'settings.json'
    p.write_text('{ not json')
    monkeypatch.setattr(reg, 'SETTINGS', str(p))
    assert reg.main() == 1
    assert p.read_text() == '{ not json'             # not overwritten
