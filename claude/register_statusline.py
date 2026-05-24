#!/usr/bin/env python3
"""Register this statusline in ~/.claude/settings.json.

Merges the `statusLine` key into the existing settings (never clobbers other
keys) and is idempotent. Invoked by `make deploy`; safe to run by hand.
"""
from __future__ import annotations

import json
import os
import sys

SETTINGS = os.path.expanduser('~/.claude/settings.json')
STATUSLINE = {
    'type': 'command',
    'command': 'python3 ~/.claude/statusline_command.py',
    'padding': 0,
}


def main() -> int:
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    data: dict = {}
    if os.path.exists(SETTINGS):
        try:
            with open(SETTINGS) as f:
                data = json.load(f)
        except ValueError:
            print(f'! {SETTINGS} is not valid JSON — leaving it untouched.',
                  file=sys.stderr)
            return 1
    if data.get('statusLine') == STATUSLINE:
        print(f'statusLine already registered in {SETTINGS}')
        return 0
    data['statusLine'] = STATUSLINE
    with open(SETTINGS, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    print(f'registered statusLine -> {SETTINGS}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
