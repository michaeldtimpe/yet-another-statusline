"""Hermetic demo for statusline-command.py.

Materialises a synthetic ~/.claude/ and project tree under a tempfile, mutates
the canonical session-info fixture in memory, and pipes the result to the
production statusline script with $HOME pointed at the tempfile. Leaves no
residue on the developer's real filesystem.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WRAPPER_DIR = Path(__file__).resolve().parent
FIXTURE_PATH = WRAPPER_DIR / 'session-info-example.json'
STATUSLINE_SCRIPT = WRAPPER_DIR.parent / 'statusline-command.py'


DEMO_USAGE_TOTALS = (16322 + 123500, 2600)


def build_synthetic_env(tmpdir: Path, session_id: str) -> None:
    claude = tmpdir / '.claude'
    project = tmpdir / 'my-project'

    (claude / 'projects' / session_id).mkdir(parents=True)
    (project / '.git' / 'refs' / 'heads').mkdir(parents=True)
    (project / 'openspec' / 'changes' / 'add-skills-row').mkdir(parents=True)
    (project / 'openspec' / 'changes' / 'port-statusline-to-python').mkdir(parents=True)

    settings = {
        'enabledPlugins': {
            'openspec@0.1.0': True,
            'frontend-design@0.3.2': True,
        }
    }
    (claude / 'settings.json').write_text(json.dumps(settings, indent=2) + '\n')

    transcript = claude / 'projects' / session_id / f'{session_id}.jsonl'
    skill_lines = [
        {'type': 'assistant', 'message': {
            'id': 'msg_demo_1',
            'role': 'assistant',
            'content': [{'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'grill-me'}}],
            'usage': {'input_tokens': 12, 'cache_creation_input_tokens': 8000, 'cache_read_input_tokens': 24000, 'output_tokens': 540},
        }},
        {'type': 'assistant', 'message': {
            'id': 'msg_demo_2',
            'role': 'assistant',
            'content': [{'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'caveman'}}],
            'usage': {'input_tokens': 6, 'cache_creation_input_tokens': 5200, 'cache_read_input_tokens': 41000, 'output_tokens': 820},
        }},
        {'type': 'assistant', 'message': {
            'id': 'msg_demo_3',
            'role': 'assistant',
            'content': [{'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'frontend-design:frontend-design'}}],
            'usage': {'input_tokens': 4, 'cache_creation_input_tokens': 3100, 'cache_read_input_tokens': 58500, 'output_tokens': 1240},
        }},
    ]
    transcript.write_text('\n'.join(json.dumps(ln) for ln in skill_lines) + '\n')

    (project / '.git' / 'HEAD').write_text('ref: refs/heads/demo\n')
    (project / '.git' / 'refs' / 'heads' / 'demo').write_text('a' * 40 + '\n')

    (project / 'openspec' / 'changes' / 'add-skills-row' / 'tasks.md').write_text(
        '- [x] one\n- [x] two\n- [x] three\n- [ ] four\n'
    )
    (project / 'openspec' / 'changes' / 'port-statusline-to-python' / 'tasks.md').write_text(
        '- [x] one\n- [ ] two\n- [ ] three\n- [ ] four\n'
    )

    seed_ts = time.time() - 30
    total_in, total_out = DEMO_USAGE_TOTALS
    seed_in = max(0, total_in - 500)
    seed_out = max(0, total_out - 80)
    (claude / 'statusline-token-rate.log').write_text(
        f'{seed_ts:.3f} {session_id} {seed_in} {seed_out}\n'
    )


def mutate_session_info(tmpdir: Path, session_id: str, raw: dict) -> str:
    project = tmpdir / 'my-project'
    raw['cwd'] = str(project)
    raw.setdefault('workspace', {})['project_dir'] = str(project)
    raw['transcript_path'] = str(
        tmpdir / '.claude' / 'projects' / session_id / f'{session_id}.jsonl'
    )
    resets = int(time.time()) + 7200
    raw.setdefault('rate_limits', {}).setdefault('five_hour', {})['resets_at'] = resets
    raw['rate_limits'].setdefault('seven_day', {})['resets_at'] = resets
    raw['thinking'] = {'enabled': True}
    raw['effort'] = {'level': 'high'}
    return json.dumps(raw)


def main() -> int:
    fixture = json.loads(FIXTURE_PATH.read_text())
    session_id = fixture['session_id']

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmpdir = Path(raw_tmp)
        build_synthetic_env(tmpdir, session_id)
        payload = mutate_session_info(tmpdir, session_id, fixture)

        env = os.environ.copy()
        env['HOME'] = str(tmpdir)

        subprocess.run(
            [sys.executable, str(STATUSLINE_SCRIPT)],
            input=payload,
            text=True,
            env=env,
            check=True,
        )
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
