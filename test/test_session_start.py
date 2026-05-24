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
    assert '→' in out            # opened → last-refresh timestamp present
    assert out.rstrip().endswith('Opus 4.7')  # model pinned last


def _ctx_info(tmp_path: Path, **ctx) -> dict:
    return {
        'session_id': 'abc', 'transcript_path': '', 'cwd': str(tmp_path),
        'model': {'id': 'claude-opus-4-7', 'display_name': 'Opus 4.7'},
        'context_window': ctx,
    }


def test_ctx_segment_uses_payload_used_percentage(monkeypatch, tmp_path: Path) -> None:
    # When the payload carries used_percentage, the ctx segment shows THAT number
    # (so it matches Claude Code's own context indicator) — not raw total/size,
    # which here would round to 0%.
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    info = _ctx_info(tmp_path, total_input_tokens=950_000, total_output_tokens=600,
                     context_window_size=1_000_000, used_percentage=97)
    out = ANSI.sub('', sl.render(info, 200))
    assert 'ctx 97%' in out


def test_ctx_segment_falls_back_to_total_over_size(monkeypatch, tmp_path: Path) -> None:
    # Older payloads omit used_percentage → fall back to total/size.
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    info = _ctx_info(tmp_path, total_input_tokens=500_000, total_output_tokens=0,
                     context_window_size=1_000_000)   # no used_percentage
    out = ANSI.sub('', sl.render(info, 200))
    assert 'ctx 50%' in out


def test_osascript_width_uses_fresh_cache(monkeypatch, tmp_path) -> None:
    # A freshly-written cache file is returned without spawning osascript, so the
    # width detector is fast on the common path.
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    (tmp_path / '.claude' / '.statusline-width').write_text('214')
    monkeypatch.setattr(sl.subprocess, 'run',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('osascript spawned')))
    assert sl._osascript_width() == 214
