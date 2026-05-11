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


def build_synthetic_env(tmpdir: Path, session_id: str, fixture_in: int, fixture_out: int) -> None:
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
        {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'grill-me'}}
        ]}},
        {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'caveman'}}
        ]}},
        {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Skill', 'input': {'skill': 'frontend-design:frontend-design'}}
        ]}},
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
    seed_in = max(0, fixture_in - 100)
    seed_out = max(0, fixture_out - 20)
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
    ctx = fixture.get('context_window', {})
    fixture_in = int(ctx.get('total_input_tokens', 0))
    fixture_out = int(ctx.get('total_output_tokens', 0))

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmpdir = Path(raw_tmp)
        build_synthetic_env(tmpdir, session_id, fixture_in, fixture_out)
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
