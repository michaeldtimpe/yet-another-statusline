"""Monaco-safety: the flat renderer must emit only standard Unicode that a
plain (non-Nerd) monospace font like Monaco renders — no Private Use Area
glyphs and no Symbols-for-Legacy-Computing. Permanent regression guard against
reintroducing Nerd Font / sparkline glyph drift."""
import json
import re
from pathlib import Path

import statusline_command as sl

ANSI = re.compile(r'\x1b\[[0-9;]*m')
SESSION = (Path(__file__).parent.parent / 'claude' / 'statusline'
           / 'session-info-example.json')


def _unsafe(text: str) -> list[str]:
    return sorted({
        f'U+{ord(c):05X}' for c in text
        if 0xE000 <= ord(c) <= 0xF8FF        # BMP Private Use Area
        or 0xF0000 <= ord(c) <= 0xFFFFD      # Supplementary PUA-A
        or 0x1FB00 <= ord(c) <= 0x1FBFF      # Symbols for Legacy Computing
    })


def test_no_pua_or_legacy_glyphs_any_theme_any_width(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    info = json.loads(SESSION.read_text())
    for theme_name, theme in sl.THEMES.items():
        for width in (50, 74, 120, 200):
            plain = ANSI.sub('', sl.render(info, width, theme=theme))
            bad = _unsafe(plain)
            assert not bad, f'{theme_name}@{width}c emitted unsafe glyphs: {bad}'


def test_render_old_payload_without_cost_or_rate_limits(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    # Backward compat: an older Claude Code payload missing cost/rate_limits/
    # thinking must still render (estimate cost fallback, no plan tag, no crash).
    (tmp_path / '.claude').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sl, 'HOME', tmp_path)
    old = {
        'session_id': 'abcdef12',
        'cwd': str(tmp_path),
        'model': {'id': 'claude-opus-4-7', 'display_name': 'Opus 4.7'},
        'context_window': {
            'total_input_tokens': 1000, 'total_output_tokens': 10,
            'context_window_size': 200000,
        },
    }
    out = sl.render(old, 120)
    assert out and not _unsafe(ANSI.sub('', out))
    assert 'plan' not in ANSI.sub('', out)  # no rate_limits => not flagged as plan
