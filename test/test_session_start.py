import json
import re
from datetime import datetime, timezone
from pathlib import Path

import statusline_command as sl

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def test_session_start_reads_first_valid_timestamp(tmp_path: Path) -> None:
    tp = tmp_path / 't.jsonl'
    tp.write_text(
        json.dumps({'type': 'user', 'timestamp': None}) + '\n' +          # null skipped
        json.dumps({'type': 'assistant', 'timestamp': '2026-05-24T16:00:41.696Z'}) + '\n' +
        json.dumps({'type': 'assistant', 'timestamp': '2026-05-24T16:30:00.000Z'}) + '\n'
    )
    got = sl._session_start(str(tp))
    expected = datetime(2026, 5, 24, 16, 0, 41, 696000, tzinfo=timezone.utc).timestamp()
    assert got == expected  # earliest non-null timestamp


def test_session_start_missing_or_empty(tmp_path: Path) -> None:
    assert sl._session_start('') is None
    assert sl._session_start(str(tmp_path / 'nope.jsonl')) is None
    empty = tmp_path / 'e.jsonl'; empty.write_text('{"type":"user"}\n')   # no timestamp
    assert sl._session_start(str(empty)) is None


def test_render_shows_uptime_when_started(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    tp = tmp_path / 't.jsonl'
    tp.write_text(json.dumps({'type': 'assistant', 'timestamp': '2026-05-24T16:00:41.696Z'}) + '\n')
    info = {
        'session_id': 'abc', 'transcript_path': str(tp), 'cwd': str(tmp_path),
        'model': {'id': 'claude-opus-4-7', 'display_name': 'Opus 4.7'},
        'context_window': {'total_input_tokens': 1000, 'total_output_tokens': 10,
                           'context_window_size': 200000},
    }
    out = ANSI.sub('', sl.render(info, 200))
    assert 'up ' in out          # uptime segment present
    assert out.rstrip().endswith('Opus 4.7')  # model pinned last
