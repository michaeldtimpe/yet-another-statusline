import re
from typing import Callable

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)
