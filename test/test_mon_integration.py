"""Integration test for the multi-session observer pipeline.

Exercises discover → classify → aggregate → format_header without needing
claude/mon.py (Phase 7).  One end-to-end test per the task spec.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from claude.mon.discovery import discover
from claude.mon.layout import aggregate_day_cost, aggregate_rate_limits, format_header
from claude.mon.lifecycle import classify
from claude.mon.tui import parse_args


def _load_mon_script():
    """Load claude/mon.py by file path.

    'claude.mon' resolves to the claude/mon/ package (it has an __init__.py),
    so the sibling claude/mon.py script — which defines tick() — isn't reachable
    via that dotted path. Load it directly instead.
    """
    mon_path = Path(__file__).parent.parent / 'claude' / 'mon.py'
    spec = importlib.util.spec_from_file_location('_mon_script_under_test', mon_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_session(session_id: str, payload: dict, age_secs: float = 0.0) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        session_id=session_id,
        jsonl_path=Path(f'/tmp/{session_id}.jsonl'),
        jsonl_mtime=time.time() - age_secs,
        payload=payload,
        payload_mtime=time.time() - age_secs,
    )

_SESSION_A     = 'aaa-111'
_SESSION_B     = 'bbb-222'
_SESSION_STALE = 'zzz-stale'

_INCLUDE = timedelta(minutes=10)


def _make_payload(session_id: str, cwd: str) -> dict:
    return {
        'session_id': session_id,
        'cwd': cwd,
        'model': {'id': 'claude-sonnet-4-6', 'display_name': 'Claude Sonnet'},
        'cost': {'total_cost_usd': 0.10},
        'rate_limits': {
            'five_hour':  {'used_percentage': 10},
            'seven_day':  {'used_percentage': 20},
        },
    }


def _write_session(
    projects_root: Path,
    payload_root: Path,
    session_id: str,
    cwd: str,
    age_seconds: float,
    now: datetime,
) -> None:
    """Write a .jsonl file and a payload .json file for one session."""
    # jsonl lives one level deep: projects_root/<subdir>/<session_id>.jsonl
    subdir = projects_root / 'my-project'
    subdir.mkdir(parents=True, exist_ok=True)
    jsonl = subdir / f'{session_id}.jsonl'
    jsonl.write_text('')
    ts = now.timestamp() - age_seconds
    os.utime(jsonl, (ts, ts))

    payload = _make_payload(session_id, cwd)
    payload_file = payload_root / f'statusline.{int(now.timestamp())}.{session_id}.json'
    payload_file.write_text(json.dumps(payload))


def test_integration_two_active_one_stale(tmp_path: Path) -> None:
    """Build a synthetic ~/.claude with 2 active + 1 stale session and run the
    discovery → lifecycle → layout pipeline, asserting:
    - only the 2 active session_ids appear in the result
    - they are in alphabetical (cwd) order
    - format_header reports '2 sessions'
    """
    now = datetime.now()

    projects_root = tmp_path / '.claude' / 'projects'
    payload_root  = tmp_path / '.claude' / 'statusline-output'
    projects_root.mkdir(parents=True)
    payload_root.mkdir(parents=True)

    _write_session(projects_root, payload_root, _SESSION_A,     '/home/user/alpha', 120,  now)
    _write_session(projects_root, payload_root, _SESSION_B,     '/home/user/beta',   60,  now)
    _write_session(projects_root, payload_root, _SESSION_STALE, '/home/user/stale', 3600, now)

    # Pass explicit paths so default-argument evaluation doesn't matter.
    from claude.mon.discovery import find_active_jsonls, index_payloads_by_session, ActiveSession

    active_jsonls   = find_active_jsonls(_INCLUDE, now, projects_root=projects_root)
    payload_index   = index_payloads_by_session(payloads_root=payload_root)

    sessions: list[ActiveSession] = []
    for jsonl_path, jsonl_mtime in active_jsonls:
        sid   = jsonl_path.stem
        entry = payload_index.get(sid)
        if entry is None:
            continue
        payload_path, payload_mtime, payload = entry
        sessions.append(ActiveSession(
            session_id=sid,
            jsonl_path=jsonl_path,
            jsonl_mtime=jsonl_mtime,
            payload=payload,
            payload_mtime=payload_mtime,
        ))

    sessions.sort(key=lambda s: (s.payload.get('cwd', ''), s.session_id))

    # --- assertions: active sessions only ---
    session_ids = [s.session_id for s in sessions]
    assert len(sessions) == 2, f'expected 2 active sessions, got {session_ids}'
    assert _SESSION_A     in session_ids
    assert _SESSION_B     in session_ids
    assert _SESSION_STALE not in session_ids

    # --- alphabetical order: alpha before beta ---
    assert sessions[0].payload.get('cwd') == '/home/user/alpha'
    assert sessions[1].payload.get('cwd') == '/home/user/beta'

    # --- lifecycle: both active sessions are bright ---
    idle_after   = timedelta(minutes=2)
    remove_after = timedelta(minutes=15)
    now_ts = now.timestamp()
    for s in sessions:
        tier = classify(s.jsonl_mtime, now_ts, idle_after, remove_after)
        assert tier == 'bright', f'session {s.session_id} expected bright, got {tier}'

    # --- header reports 2 sessions ---
    five_h, seven_d = aggregate_rate_limits(sessions)
    day_cost        = aggregate_day_cost(sessions)
    header          = format_header(len(sessions), five_h, seven_d, day_cost, 120)

    # Strip ANSI escapes for plain-text assertion.
    plain_header = re.sub(r'\033\[[0-9;]*m', '', header)
    assert '2 sessions' in plain_header, f'header does not contain "2 sessions": {plain_header!r}'


def test_tick_erases_stale_content_every_line(monkeypatch, capsys) -> None:
    """tick() must erase-to-end-of-line on every row and erase-to-end-of-screen
    after the frame, so a shrinking session list doesn't leave stale rows on screen.
    """
    mon = _load_mon_script()

    session = _fake_session('s1', {'cost': {'total_cost_usd': 1.0}})
    monkeypatch.setattr(mon, 'discover', lambda include_after, now: [session])
    monkeypatch.setattr(
        mon, 'render', lambda payload, width, bg_shift=None, theme=None, record=True: 'BOX'
    )
    monkeypatch.setattr(
        mon.shutil, 'get_terminal_size', lambda fallback=None: os.terminal_size((80, 10))
    )

    args = parse_args([])
    mon.tick(args)

    out = capsys.readouterr().out
    assert out.startswith('\x1b[H'), f'frame does not start at cursor-home: {out!r}'
    body = out[len('\x1b[H'):]
    assert body.endswith('\x1b[J'), f'frame does not end with erase-to-end-of-screen: {out!r}'
    body = body[:-len('\x1b[J')]

    lines = body.split('\n')
    assert len(lines) > 1, 'expected a multi-line frame'
    for line in lines:
        assert line.endswith('\x1b[K'), f'line missing erase-to-end-of-line: {line!r}'


def test_tick_pairs_sessions_with_boxes_across_skips_and_clipping(monkeypatch) -> None:
    """visible_sessions must track the surviving (session, box) prefix — not a fragile
    zip()+membership match, which misaligns when a render is skipped and breaks when two
    boxes render identically.
    """
    mon = _load_mon_script()

    skipped  = _fake_session('skipped',  {'cost': {'total_cost_usd': 999.0}})
    shown    = _fake_session('shown',    {'cost': {'total_cost_usd': 1.0}})
    hidden   = _fake_session('hidden',   {'cost': {'total_cost_usd': 99.0}})
    # Same jsonl_mtime so 'shown' and 'hidden' get identical age labels — the
    # duplicate-content case that breaks a membership-based (box in visible_boxes) match.
    hidden.jsonl_mtime = shown.jsonl_mtime

    def fake_render(payload, width, bg_shift=None, theme=None, record=True):
        if payload.get('total_cost_usd_marker') == 'skip':
            return ''
        return 'DUPBOX'  # 'shown' and 'hidden' render identically on purpose

    skipped.payload = {'total_cost_usd_marker': 'skip'}
    monkeypatch.setattr(mon, 'discover', lambda include_after, now: [skipped, shown, hidden])
    monkeypatch.setattr(mon, 'render', fake_render)
    # Only tall enough for one 2-line box (age label + 'DUPBOX') in the body.
    monkeypatch.setattr(
        mon.shutil, 'get_terminal_size', lambda fallback=None: os.terminal_size((80, 4))
    )

    captured = {}
    real_aggregate_day_cost = mon.aggregate_day_cost

    def spy_aggregate_day_cost(sessions):
        captured['visible_sessions'] = list(sessions)
        return real_aggregate_day_cost(sessions)

    monkeypatch.setattr(mon, 'aggregate_day_cost', spy_aggregate_day_cost)

    args = parse_args([])
    mon.tick(args)

    assert captured['visible_sessions'] == [shown], (
        f'expected only the visible "shown" session, got: {captured["visible_sessions"]}'
    )


def test_tick_renders_with_record_false(monkeypatch) -> None:
    """mon re-renders old stored payloads every 2s; it must not re-write state
    (token log, rate sample, billing cache) on each redraw, so it always calls
    render(..., record=False).
    """
    mon = _load_mon_script()

    sessions = [_fake_session('a', {}), _fake_session('b', {})]
    monkeypatch.setattr(mon, 'discover', lambda include_after, now: sessions)
    monkeypatch.setattr(
        mon.shutil, 'get_terminal_size', lambda fallback=None: os.terminal_size((80, 20))
    )

    calls = []

    def spy_render(payload, width, bg_shift=None, theme=None, record=True):
        calls.append(record)
        return 'BOX'

    monkeypatch.setattr(mon, 'render', spy_render)

    args = parse_args([])
    mon.tick(args)

    assert len(calls) == len(sessions), f'expected one render() call per session, got {calls}'
    assert all(record is False for record in calls), (
        f'expected every render() call to pass record=False, got {calls}'
    )
