#!/usr/bin/env python3
'Claude Code statusLine command (Python port).'

from __future__ import annotations
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


# Load the themes module via importlib because this script runs as a top-level
# file (not inside a package). The same shim is used by test/conftest.py.
_THEMES_PATH = Path(__file__).resolve().parent / 'statusline' / 'themes.py'
_themes_spec = importlib.util.spec_from_file_location('statusline_themes', _THEMES_PATH)
assert _themes_spec is not None and _themes_spec.loader is not None
themes = importlib.util.module_from_spec(_themes_spec)
sys.modules['statusline_themes'] = themes
_themes_spec.loader.exec_module(themes)
Theme        = themes.Theme
ModelColors  = themes.ModelColors
THEMES       = themes.THEMES
CLAUDE_DARK  = themes.CLAUDE_DARK


HOME       = Path(os.path.expanduser('~'))
MIN_WIDTH    = 40
MAX_WIDTH    = 160
NARROW_WIDTH = 55
MEDIUM_WIDTH = 80
SOFT_LIMIT = 150_000
_ANSI_RE   = re.compile(r'\x1b\[[0-9;]*m')


def terminal_width() -> int:
    try:
        w = int(subprocess.run(["tmux", "display-message", "-p", "'#{pane_width}'"], capture_output=True, text=True).stdout.strip().replace("'", ""))
        if w > 0:
            return w
    except (OSError, ValueError):
        pass
    try:
        w = int((HOME / '.claude' / 'terminal-width').read_text().strip())
        if w > 0:
            return w
    except (OSError, ValueError):
        pass
    try:
        cols = int(os.environ.get('COLUMNS', '0'))
        if cols > 0:
            return cols
    except ValueError:
        pass
    w = shutil.get_terminal_size(fallback=(0, 0)).columns
    if w > 0:
        return w
    for fd in (2, 1, 0):
        try:
            return os.get_terminal_size(fd).columns
        except OSError:
            pass
    try:
        tty_fd = os.open('/dev/tty', os.O_RDONLY)
        try:
            return os.get_terminal_size(tty_fd).columns
        finally:
            os.close(tty_fd)
    except OSError:
        pass
    return MAX_WIDTH

RESET  = '\033[0m'
BOLD   = '\033[1m'
ITALIC = '\033[3m'

CLR_GREY_DIM   = '\033[38;5;244m'
CLR_GREY_DARK  = '\033[38;5;238m'
CLR_BORDER_OFF = '\033[38;5;242m'
CLR_SKY_BLUE   = '\033[38;5;75m'
CLR_GREEN_OK   = '\033[38;5;114m'
CLR_GREEN_DIM  = '\033[38;5;77m'
CLR_GREEN_BRT  = '\033[38;5;46m'
CLR_PURPLE     = '\033[38;5;183m'
CLR_GOLD       = '\033[38;5;222m'
CLR_YELLOW     = '\033[38;5;226m'
CLR_YELLOW_BRT = '\033[38;5;11m'
CLR_CYAN       = '\033[38;5;116m'
CLR_CYAN_DIM   = '\033[38;5;244m'
CLR_CYAN_DAY   = '\033[38;5;109m'
CLR_CYAN_DAY_DIM = '\033[38;5;240m'
CLR_CYAN_ICON  = '\033[38;5;117m'
CLR_PINK       = '\033[38;5;210m'
CLR_PEACH      = '\033[38;5;216m'
CLR_WHITE_BRT  = '\033[38;5;15m'
CLR_WARN       = '\033[38;5;214m'
CLR_ALERT      = '\033[38;5;167m'

# Section markers \u2014 plain text / standard-Unicode only (Monaco-safe; NO Nerd
# Font Private Use Area glyphs). Kept as named constants so every visible symbol
# is auditable and future edits can't silently reintroduce PUA drift.
ICON_COST     = ''         # cost row \u2014 the '$' lives in the formatted figure
ICON_TOK_RATE = ''         # token-rate \u2014 the 't/m' suffix carries the meaning
GLYPH_MODEL    = ''        # model row \u2014 the name stands alone
GLYPH_THINKING = ''        # effort renders as a word (e.g. 'xhigh')
GLYPH_FAST     = ''        # fast-mode renders via the effort word
GLYPH_FOLDER   = ''        # path row \u2014 the path stands alone
GLYPH_SUBAGENT = ''        # (subagent rows removed)
GLYPH_SUBAGENT_ROW = '>'   # (subagent rows removed; ASCII fallback)
GLYPH_TASKS    = ''        # (task row removed)
GLYPH_SKILLS  = 'skills'   # skills label
GLYPH_PLUGINS = 'plugins'  # plugins label
GLYPH_HELPER   = '5h'      # five-hour rate-limit label
GLYPH_TRASH    = '-'       # git deleted count
GLYPH_RENAMED  = 'R'       # git renamed count
GLYPH_TOK_IN_ACTIVE  = '\u2193' # token input  (standard arrow; no active/idle split)
GLYPH_TOK_OUT_ACTIVE = '\u2191' # token output (standard arrow)

def _is_wide(ch: str) -> bool:
    cp = ord(ch)
    return 0x1F300 <= cp <= 0x1FAFF


def _visible_width(s: str) -> int:
    plain = _ANSI_RE.sub('', s)
    return sum(2 if _is_wide(ch) else 1 for ch in plain)


def _middle_ellipsis(text: str, max_w: int) -> str:
    if max_w <= 1:
        return '…'
    if _visible_width(text) <= max_w:
        return text
    left_vis  = (max_w - 1) // 2
    right_vis = max_w - 1 - left_vis

    # Tokenise into (is_escape, string) pairs to preserve ANSI across the cut.
    tokens: list[tuple[bool, str]] = []
    i = 0
    while i < len(text):
        m = _ANSI_RE.match(text, i)
        if m:
            tokens.append((True, m.group()))
            i = m.end()
        else:
            tokens.append((False, text[i]))
            i += 1

    def _take(toks: list[tuple[bool, str]], n: int) -> list[str]:
        out: list[str] = []
        seen = 0
        for is_esc, tok in toks:
            if is_esc:
                out.append(tok)
            elif seen < n:
                out.append(tok)
                seen += 1
            else:
                break
        return out

    prefix = _take(tokens, left_vis)
    suffix = _take(list(reversed(tokens)), right_vis)
    suffix.reverse()

    result = ''.join(prefix) + '…' + ''.join(suffix)
    if _visible_width(result) <= max_w:
        return result
    # Trim one visible char from prefix to fix wide-char overshoot.
    for j in range(len(prefix) - 1, -1, -1):
        if not _ANSI_RE.fullmatch(prefix[j]):
            prefix.pop(j)
            break
    return ''.join(prefix) + '…' + ''.join(suffix)


class TokenAccounting:
    @staticmethod
    def rates_for(model_name: str) -> tuple[float, float]:
        m = model_name.lower()
        if 'opus' in m:
            return 15.00, 75.00
        if 'haiku' in m:
            return 0.80, 4.00
        return 3.00, 15.00

    @staticmethod
    def session_cost(model: Model, usage: TranscriptUsage) -> float:
        rate_in, rate_out = TokenAccounting.rates_for(
            model.display_name or model.id
        )
        cost = (
            usage.input_tokens * rate_in
            + usage.cache_creation_input_tokens * rate_in * 1.25
            + usage.cache_read_input_tokens * rate_in * 0.1
            + usage.output_tokens * rate_out
        )
        return cost / 1_000_000

    @staticmethod
    def day_cost(model: Model, token_log: TokenLog) -> float:
        rate_in, rate_out = TokenAccounting.rates_for(
            model.display_name or model.id
        )
        cost = (
            token_log.day_in * rate_in
            + token_log.day_cache_read * rate_in * 0.1
            + token_log.day_out * rate_out
        )
        return cost / 1_000_000


class Model(NamedTuple):
    id: str = ''
    display_name: str = ''

    @classmethod
    def from_dict(cls, d: dict) -> Model:
        return cls(id=d.get('id', ''), display_name=d.get('display_name', ''))

    @property
    def cost_rates(self) -> tuple[float, float]:
        return TokenAccounting.rates_for(self.display_name or self.id)


class OutputStyle(NamedTuple):
    name: str = 'default'

    @classmethod
    def from_dict(cls, d: dict) -> OutputStyle:
        return cls(name=d.get('name', 'default'))


class Effort(NamedTuple):
    level: str = ''

    @classmethod
    def from_dict(cls, d: dict) -> Effort:
        return cls(level=d.get('level', ''))


class Thinking(NamedTuple):
    enabled: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> Thinking:
        return cls(enabled=bool(d.get('enabled', False)))


class CurrentUsage(NamedTuple):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> CurrentUsage:
        return cls(
            input_tokens                = d.get('input_tokens', 0),
            output_tokens               = d.get('output_tokens', 0),
            cache_creation_input_tokens = d.get('cache_creation_input_tokens', 0),
            cache_read_input_tokens     = d.get('cache_read_input_tokens', 0),
        )


class RateBucket(NamedTuple):
    used_percentage: float = 0.0
    resets_at: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> RateBucket:
        return cls(
            used_percentage = round(float(d.get('used_percentage', 0.0)), 2),
            resets_at       = d.get('resets_at', 0),
        )


@dataclass
class Workspace:
    current_dir: str = ''
    project_dir: str = ''
    added_dirs: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> Workspace:
        return cls(
            current_dir = d.get('current_dir', ''),
            project_dir = d.get('project_dir', ''),
            added_dirs  = d.get('added_dirs') or [],
        )

    @property
    def plugins(self) -> str:
        seen: dict[str, None] = {}
        candidates = [HOME / '.claude' / 'settings.json']
        if self.project_dir:
            candidates.append(Path(self.project_dir) / '.claude' / 'settings.json')
        for sf in candidates:
            if not sf.is_file():
                continue
            try:
                data = json.loads(sf.read_text())
            except Exception:
                continue
            for key, val in (data.get('enabledPlugins') or {}).items():
                if val is True:
                    name = key.split('@', 1)[0]
                    if name not in seen:
                        seen[name] = None
        return ','.join(seen.keys())


@dataclass
class Cost:
    # None means the payload omitted the field (older Claude Code) — distinct
    # from a real 0.0, so the renderer can fall back to the estimate only when
    # the authoritative cost is genuinely absent.
    total_cost_usd: float | None = None
    total_duration_ms: int = 0
    total_api_duration_ms: int = 0
    total_lines_added: int = 0
    total_lines_removed: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> Cost:
        return cls(
            total_cost_usd        = d.get('total_cost_usd'),
            total_duration_ms     = d.get('total_duration_ms', 0),
            total_api_duration_ms = d.get('total_api_duration_ms', 0),
            total_lines_added     = d.get('total_lines_added', 0),
            total_lines_removed   = d.get('total_lines_removed', 0),
        )


@dataclass
class ContextWindow:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    context_window_size: int = 0
    current_usage: CurrentUsage = field(default_factory=CurrentUsage)
    used_percentage: float | None = None
    remaining_percentage: float | None = None

    @classmethod
    def from_dict(cls, d: dict) -> ContextWindow:
        return cls(
            total_input_tokens   = d.get('total_input_tokens', 0),
            total_output_tokens  = d.get('total_output_tokens', 0),
            context_window_size  = d.get('context_window_size', 0),
            current_usage        = CurrentUsage.from_dict(d.get('current_usage') or {}),
            used_percentage      = d.get('used_percentage'),
            remaining_percentage = d.get('remaining_percentage'),
        )


@dataclass
class RateLimits:
    five_hour: RateBucket = field(default_factory=RateBucket)
    seven_day: RateBucket = field(default_factory=RateBucket)

    @classmethod
    def from_dict(cls, d: dict) -> RateLimits:
        return cls(
            five_hour = RateBucket.from_dict(d.get('five_hour')  or {}),
            seven_day = RateBucket.from_dict(d.get('seven_day') or {}),
        )


@dataclass
class SessionInfo:
    session_id: str = ''
    transcript_path: str = ''
    cwd: str = ''
    model: Model = field(default_factory=Model)
    workspace: Workspace = field(default_factory=Workspace)
    version: str = ''
    output_style: OutputStyle = field(default_factory=OutputStyle)
    cost: Cost = field(default_factory=Cost)
    context_window: ContextWindow = field(default_factory=ContextWindow)
    exceeds_200k_tokens: bool = False
    effort: Effort = field(default_factory=Effort)
    thinking: Thinking = field(default_factory=Thinking)
    fast_mode: bool = False
    rate_limits: RateLimits = field(default_factory=RateLimits)

    @classmethod
    def from_dict(cls, d: dict) -> SessionInfo:
        return cls(
            session_id          = d.get('session_id', ''),
            transcript_path     = d.get('transcript_path', ''),
            cwd                 = d.get('cwd', ''),
            model               = Model.from_dict(d.get('model') or {}),
            workspace           = Workspace.from_dict(d.get('workspace') or {}),
            version             = d.get('version', ''),
            output_style        = OutputStyle.from_dict(d.get('output_style') or {}),
            cost                = Cost.from_dict(d.get('cost') or {}),
            context_window      = ContextWindow.from_dict(d.get('context_window') or {}),
            exceeds_200k_tokens = d.get('exceeds_200k_tokens', False),
            effort              = Effort.from_dict(d.get('effort') or {}),
            thinking            = Thinking.from_dict(d.get('thinking') or {}),
            fast_mode           = bool(d.get('fast_mode', False)),
            rate_limits         = RateLimits.from_dict(d.get('rate_limits') or {}),
        )

    @property
    def short_pwd(self) -> str:
        home = str(HOME)
        p = self.cwd
        if p.startswith(home):
            p = '~' + p[len(home):]
        parts = p.split('/')
        last = len(parts) - 1
        out_parts = []
        for i, seg in enumerate(parts):
            if i == last or seg == '' or seg == '~':
                out_parts.append(seg)
            else:
                out_parts.append(seg[0])
        return '/'.join(out_parts)

    @property
    def model_name(self) -> str:
        name = self.model.display_name or self.model.id or 'unknown'
        return name.replace('(1M context)', '1M').replace('  ', ' ').strip()

    @property
    def model_thinking(self) -> str:
        if self.thinking.enabled and self.effort.level:
            return f'{self.effort.level}/fast' if self.fast_mode else self.effort.level
        if self.fast_mode:
            return 'fast'
        return ''

    @property
    def plugin_names(self) -> str:
        return self.workspace.plugins


def compute_session_cost(model: Model, usage: TranscriptUsage) -> float:
    return TokenAccounting.session_cost(model, usage)


def compute_day_cost(model: Model, token_log: TokenLog) -> float:
    return TokenAccounting.day_cost(model, token_log)


def effective_session_cost(session: SessionInfo, usage: TranscriptUsage) -> float:
    """Session cost, preferring the payload's authoritative billed figure
    (`cost.total_cost_usd`). Falls back to the token×rate estimate only when the
    payload omitted it (older Claude Code); a real 0.0 is honoured."""
    payload = session.cost.total_cost_usd
    if isinstance(payload, (int, float)) and not isinstance(payload, bool) and payload >= 0:
        return float(payload)
    return compute_session_cost(session.model, usage)


@dataclass
class TokenLog:
    day_in: int = 0
    day_cache_read: int = 0
    day_out: int = 0

    @classmethod
    def update(cls, session_id: str, today: str, total_in: int, cache_read: int, total_out: int) -> TokenLog:
        log = HOME / '.claude' / 'statusline-tokens.log'
        lines = []
        if log.exists():
            for ln in log.read_text().splitlines():
                parts = ln.split()
                if len(parts) >= 2 and parts[1] == session_id:
                    continue
                lines.append(ln)
        if session_id and (total_in > 0 or cache_read > 0 or total_out > 0):
            lines.append(f'{today} {session_id} {total_in} {cache_read} {total_out}')
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text('\n'.join(lines) + '\n')
        day_in = day_cache_read = day_out = 0
        for ln in lines:
            parts = ln.split()
            if len(parts) < 4 or parts[0] != today:
                continue
            try:
                if len(parts) == 6:
                    day_in += int(parts[2])
                    day_out += int(parts[3])
                elif len(parts) >= 5:
                    day_in += int(parts[2])
                    day_cache_read += int(parts[3])
                    day_out += int(parts[4])
                else:
                    day_in += int(parts[2])
                    day_out += int(parts[3])
            except ValueError:
                pass
        return cls(day_in=day_in, day_cache_read=day_cache_read, day_out=day_out)



class TokenRate:
    WINDOW = float(os.environ.get('STATUSLINE_TOKEN_WINDOW', '60'))
    KEEP = 300.0

    @classmethod
    def update(cls, session_id: str, total_in: int, total_out: int) -> int:
        if not session_id:
            return 0
        log = HOME / '.claude' / 'statusline-token-rate.log'
        now = time.time()
        rows: list[tuple[float, str, int, int]] = []
        if log.exists():
            for ln in log.read_text().splitlines():
                parts = ln.split()
                if len(parts) < 4:
                    continue
                try:
                    ts = float(parts[0])
                    ti = int(parts[2])
                    to = int(parts[3])
                except ValueError:
                    continue
                if now - ts > cls.KEEP:
                    continue
                rows.append((ts, parts[1], ti, to))
        rows.append((now, session_id, total_in, total_out))
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text('\n'.join(f'{ts:.3f} {sid} {ti} {to}' for ts, sid, ti, to in rows) + '\n')
        except OSError:
            pass
        samples = [(ts, ti, to) for ts, sid, ti, to in rows if sid == session_id and now - ts <= cls.WINDOW]
        if len(samples) < 2:
            return 0
        samples.sort()
        _, ti0, to0 = samples[0]
        _, ti1, to1 = samples[-1]
        return max(0, (ti1 + to1) - (ti0 + to0))

    @classmethod
    def history(cls, session_id: str, n_buckets: int, window: float) -> list[int]:
        if n_buckets <= 0 or not session_id:
            return []
        log = HOME / '.claude' / 'statusline-token-rate.log'
        now = time.time()
        samples: list[tuple[float, int, int]] = []
        if log.exists():
            for ln in log.read_text().splitlines():
                parts = ln.split()
                if len(parts) < 4:
                    continue
                try:
                    ts = float(parts[0])
                    sid = parts[1]
                    ti = int(parts[2])
                    to = int(parts[3])
                except ValueError:
                    continue
                if sid == session_id and now - ts <= window + window / n_buckets:
                    samples.append((ts, ti, to))
        if len(samples) < 2:
            return [0] * n_buckets
        samples.sort()
        bucket_size = window / n_buckets
        last_bucket  = int(now // bucket_size)
        first_bucket = last_bucket - n_buckets + 1
        buckets = [0] * n_buckets
        for i in range(len(samples) - 1):
            ts0, ti0, to0 = samples[i]
            ts1, ti1, to1 = samples[i + 1]
            delta = max(0, (ti1 + to1) - (ti0 + to0))
            if delta == 0:
                continue
            midpoint = (ts0 + ts1) / 2
            abs_bucket = int(midpoint // bucket_size)
            if first_bucket <= abs_bucket <= last_bucket:
                buckets[abs_bucket - first_bucket] += delta
        return buckets

    @classmethod
    def recently_active(cls, session_id: str, window: float = 10.0) -> tuple[bool, bool]:
        """Return (in_active, out_active) — True if that count grew in the last `window` seconds."""
        if not session_id:
            return False, False
        log = HOME / '.claude' / 'statusline-token-rate.log'
        if not log.exists():
            return False, False
        now = time.time()
        samples: list[tuple[float, int, int]] = []
        for ln in log.read_text().splitlines():
            parts = ln.split()
            if len(parts) < 4:
                continue
            try:
                ts, sid, ti, to = float(parts[0]), parts[1], int(parts[2]), int(parts[3])
            except ValueError:
                continue
            if sid == session_id and now - ts <= window:
                samples.append((ts, ti, to))
        if len(samples) < 2:
            return False, False
        samples.sort()
        ti0, to0 = samples[0][1], samples[0][2]
        ti1, to1 = samples[-1][1], samples[-1][2]
        return ti1 > ti0, to1 > to0


@dataclass
class GitInfo:
    branch: str = ''
    commit: str = ''
    modified: int = 0
    untracked: int = 0
    deleted: int = 0
    renamed: int = 0

    @classmethod
    def from_cwd(cls, cwd: str) -> GitInfo:
        repo, gitdir   = cls._find_repo(cwd)
        branch, commit = cls._read_head(gitdir)
        modified = untracked = deleted = renamed = 0
        if branch:
            modified, untracked, deleted, renamed = cls._dirty(repo)
        return cls(
            branch    = branch,
            commit    = commit,
            modified  = modified,
            untracked = untracked,
            deleted   = deleted,
            renamed   = renamed,
        )

    @staticmethod
    def _find_repo(cwd: str) -> tuple[str, str]:
        curr = Path(cwd) if cwd else None
        while curr:
            if (curr / '.git').exists():
                return str(curr), str(curr / '.git')
            if curr == curr.parent:
                break
            curr = curr.parent
        return '', ''

    @staticmethod
    def _read_head(gitdir: str) -> tuple[str, str]:
        if not gitdir:
            return '', ''
        head_path = Path(gitdir) / 'HEAD'
        if not head_path.is_file():
            return '', ''
        try:
            head = head_path.read_text().strip()
        except OSError:
            return '', ''
        branch = ''
        if head.startswith('ref:'):
            branch = head.rsplit('/', 1)[-1]
        elif head:
            branch = f'd:{head[:7]}'
        commit = ''
        if branch and not branch.startswith('d:'):
            ref = Path(gitdir) / 'refs' / 'heads' / branch
            if ref.is_file():
                try:
                    commit = ref.read_text().strip()[:9]
                except OSError:
                    pass
        if not commit:
            orig = Path(gitdir) / 'ORIG_HEAD'
            if orig.is_file():
                try:
                    commit = orig.read_text().strip()[:9]
                except OSError:
                    pass
        return branch, commit

    @staticmethod
    def _dirty(repo: str) -> tuple[int, int, int, int]:
        modified = untracked = deleted = renamed = 0
        if not repo:
            return modified, untracked, deleted, renamed
        try:
            r = subprocess.run(
                ['git', '-C', repo, 'status', '--porcelain=v1', '-z',
                 '--untracked-files=normal'],
                capture_output=True, text=True, timeout=2,
            )
        except Exception:
            return modified, untracked, deleted, renamed
        entries = [e for e in r.stdout.split('\0') if e]
        i = 0
        while i < len(entries):
            entry = entries[i]
            if len(entry) < 2:
                i += 1
                continue
            x, y = entry[0], entry[1]
            if x == 'R' or y == 'R':
                renamed += 1
                i += 2  # rename consumes a second NUL-separated original-name field
                continue
            if x == '?' and y == '?':
                untracked += 1
            elif x == 'A' or y == 'A':
                untracked += 1
            elif x == 'D' or y == 'D':
                deleted += 1
            elif x == 'M' or y == 'M':
                modified += 1
            i += 1
        return modified, untracked, deleted, renamed


@dataclass
class TranscriptUsage:
    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0

    @classmethod
    def from_transcript(cls, transcript_path: str) -> TranscriptUsage:
        if not transcript_path:
            return cls()
        p = Path(transcript_path)
        if not p.is_file():
            return cls()
        seen: set[str] = set()
        ti = cc = cr = to = 0
        try:
            with p.open('r', errors='ignore') as fh:
                for ln in fh:
                    if '"usage"' not in ln or '"assistant"' not in ln:
                        continue
                    try:
                        d = json.loads(ln)
                    except (ValueError, TypeError):
                        continue
                    msg = d.get('message') or {}
                    mid = msg.get('id')
                    if not mid or mid in seen:
                        continue
                    seen.add(mid)
                    u = msg.get('usage') or {}
                    ti += u.get('input_tokens', 0) or 0
                    cc += u.get('cache_creation_input_tokens', 0) or 0
                    cr += u.get('cache_read_input_tokens', 0) or 0
                    to += u.get('output_tokens', 0) or 0
        except OSError:
            return cls()
        return cls(
            input_tokens                = ti,
            cache_creation_input_tokens = cc,
            cache_read_input_tokens     = cr,
            output_tokens               = to,
        )

    @property
    def billed_in(self) -> int:
        return self.input_tokens + self.cache_creation_input_tokens

    @property
    def cache_read(self) -> int:
        return self.cache_read_input_tokens

    @property
    def out(self) -> int:
        return self.output_tokens


def fmt_tok(n: int) -> str:
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f}M'
    if n >= 1000:
        return f'{n/1000:.1f}K'
    return str(n)


def fmt_dur(seconds: float) -> str:
    s = int(seconds)
    if s < 0:
        s = 0
    if s < 60:
        return f'{s}s'
    if s < 3600:
        return f'{s // 60}m{s % 60:02d}s'
    return f'{s // 3600}h{(s % 3600) // 60:02d}m'


def model_key(name: str) -> str:
    m = name.lower()
    if 'opus'   in m: return 'opus'
    if 'sonnet' in m: return 'sonnet'
    if 'haiku'  in m: return 'haiku'
    return 'other'


class Renderer:
    def __init__(self, bg_shift: str = 'warm', theme: Theme | None = None) -> None:
        self.bg_shift = bg_shift if bg_shift in ('warm', 'cool') else 'warm'
        self.theme    = theme if theme is not None else CLAUDE_DARK
        self._apply_theme(self.theme)

    def _apply_theme(self, t: Theme) -> None:
        self.BORDER      = t.border
        self.PWD         = t.pwd
        self.BRANCH      = t.branch
        self.COMMIT      = t.commit
        self.SESSION     = t.session
        self.MODEL       = t.model
        self.SKILLS      = t.skills
        self.TIME        = t.time
        self.TOK         = t.tok
        self.TOK_DIM     = t.tok_dim
        self.TOK_DAY     = t.tok_day
        self.TOK_DAY_DIM = t.tok_day_dim
        self.COST        = t.cost
        self.BAR_FILL    = t.bar_fill
        self.BAR_EMPTY   = t.bar_empty
        self.DIM_GREEN   = t.dim_green
        self.LABEL       = t.label
        self.CTX         = t.ctx
        self.BOLDW       = BOLD + t.white_brt
        self.BOLDY       = t.tok_arrow
        self.DIRTY       = t.dirty
        self.ICON_PATH   = t.icon_path
        self.ARROW       = t.arrow
        self.TOK_ICON    = t.tok_icon
        self.OPUS        = t.models['opus'].label
        self.SONNET      = t.models['sonnet'].label
        self.HAIKU       = t.models['haiku'].label
        self.safe        = t.safe
        self.warn        = t.warn
        self.alert       = t.alert
        self.yellow      = t.yellow
        self.white_brt   = t.white_brt
        self.pill_fg_dark    = t.pill_fg_dark
        self.pill_fg_light   = t.pill_fg_light
        self.SPEC_GRADIENTS  = t.spec_gradients
        self.spec_empty_ansi = t.spec_empty_ansi

    R         = RESET
    BORDER    = CLR_GREY_DIM
    PWD       = CLR_SKY_BLUE
    BRANCH    = CLR_GREEN_OK
    COMMIT    = CLR_GREY_DIM
    SESSION   = CLR_GREY_DIM
    MODEL     = CLR_PURPLE
    SKILLS    = CLR_GOLD
    TIME      = CLR_GREY_DIM
    TOK       = CLR_CYAN
    TOK_DIM   = CLR_CYAN_DIM
    TOK_DAY     = CLR_CYAN_DAY
    TOK_DAY_DIM = CLR_CYAN_DAY_DIM
    COST      = CLR_PINK
    BAR_FILL  = CLR_GREEN_OK
    BAR_EMPTY = CLR_GREY_DARK
    DIM_GREEN = CLR_GREEN_DIM
    LABEL     = CLR_GREY_DIM
    CTX       = CLR_PEACH
    BOLDW     = BOLD + CLR_WHITE_BRT
    BOLDY     = CLR_YELLOW
    DIRTY     = CLR_WARN
    ICON_PATH = CLR_CYAN_ICON
    ARROW     = CLR_GREEN_BRT
    TOK_ICON  = CLR_YELLOW_BRT
    OPUS      = CLR_YELLOW
    SONNET    = CLR_GREEN_OK
    HAIKU     = CLR_SKY_BLUE

    def model_colour(self, model_name: str) -> str:
        return self.theme.models[model_key(model_name)].label

    def fill_colour(self, pct: float) -> str:
        if pct >= 90:
            return self.alert
        if pct >= 70:
            return self.warn
        return self.safe


def resolve_theme(cli_name: str | None) -> Theme:
    """Layered theme selection: CLI → env → config file → CLAUDE_DARK."""
    if cli_name and cli_name in THEMES:
        return THEMES[cli_name]
    env = os.environ.get('CLAUDE_STATUSLINE_THEME', '').strip()
    if env in THEMES:
        return THEMES[env]
    try:
        cfg = (HOME / '.claude' / 'statusline-theme').read_text().strip()
        if cfg in THEMES:
            return THEMES[cfg]
    except OSError:
        pass
    return CLAUDE_DARK


def _fmt_reset(resets_at: float) -> str:
    """'T-H:MM' until a rate-limit window resets, or '' if unknown/past."""
    if not resets_at:
        return ''
    delta = resets_at - time.time()
    if delta <= 0:
        return ''
    h, m = int(delta // 3600), int((delta % 3600) // 60)
    return f'T-{h}:{m:02d}'


def render_lines(session: SessionInfo, width: int, r: Renderer) -> list[str]:
    """Single borderless line of ` · `-separated segments. Responsive: segments
    are dropped right-to-left when the terminal is too narrow, and the location
    segment is truncated as a last resort. Priority (kept longest, left → right):
    location, model, context, tokens, cache, rate, 5h, 7d, plan.

        <path> ∈ <branch>/<commit> <dirty> · <model> <effort> · ctx % <used>/<size>
          · ↓in ↑out · cache N · <rate>/m · 5h % T-H:MM · 7d % · plan
    """
    SEP   = f' {r.LABEL}·{r.R} '
    ctx   = session.context_window
    total = ctx.total_input_tokens + ctx.total_output_tokens
    size  = ctx.context_window_size or 0

    git   = GitInfo.from_cwd(session.cwd)
    usage = TranscriptUsage.from_transcript(session.transcript_path)
    today = datetime.now().strftime('%Y-%m-%d')
    TokenLog.update(session.session_id, today, usage.billed_in, usage.cache_read, usage.out)
    tok_rate    = TokenRate.update(session.session_id, usage.billed_in, usage.out)
    five, seven = session.rate_limits.five_hour, session.rate_limits.seven_day

    # location (always present; truncated last)
    loc = f'{r.PWD}{session.short_pwd}{r.R}'
    if git.branch:
        loc += f' {r.LABEL}∈{r.R} {r.BRANCH}{git.branch}{r.R}'
        if git.commit:
            loc += f'{r.COMMIT}/{git.commit}{r.R}'
        dirty = ''
        if git.untracked: dirty += f'{r.DIRTY}•{git.untracked}{r.R}'
        if git.modified:  dirty += f'{r.DIRTY}*{git.modified}{r.R}'
        if git.deleted:   dirty += f'{r.DIRTY}-{git.deleted}{r.R}'
        if git.renamed:   dirty += f'{r.DIRTY}R{git.renamed}{r.R}'
        if dirty:
            loc += ' ' + dirty

    model = f'{r.model_colour(session.model_name)}{session.model_name}{r.R}'
    if session.model_thinking:
        model += f' {r.MODEL}{ITALIC}{session.model_thinking}{r.R}'

    ctx_pct = (total / size * 100) if size else 0.0
    ctx_clr = r.fill_colour(total / SOFT_LIMIT * 100)
    ctx_seg = (f'{r.LABEL}ctx {ctx_clr}{ctx_pct:.0f}%{r.R} '
               f'{r.CTX}{fmt_tok(total)}{r.LABEL}/{fmt_tok(size)}{r.R}')
    io_seg    = (f'{r.LABEL}↓{r.R}{r.TOK}{fmt_tok(usage.billed_in)}{r.R} '
                 f'{r.LABEL}↑{r.R}{r.TOK}{fmt_tok(usage.out)}{r.R}')
    cache_seg = f'{r.LABEL}cache {r.TOK_DIM}{fmt_tok(usage.cache_read)}{r.R}'
    rate_seg  = f'{r.TOK_ICON}{fmt_tok(tok_rate)}{r.R}{r.LABEL}/m{r.R}'

    segs = [loc, model, ctx_seg, io_seg, cache_seg, rate_seg]

    if five.resets_at or seven.resets_at or five.used_percentage or seven.used_percentage:
        reset    = _fmt_reset(five.resets_at)
        five_seg = f'{r.LABEL}5h {r.fill_colour(float(five.used_percentage or 0))}{int(five.used_percentage or 0)}%{r.R}'
        if reset:
            five_seg += f' {r.COMMIT}{reset}{r.R}'
        seven_seg = f'{r.LABEL}7d {r.fill_colour(float(seven.used_percentage or 0))}{int(seven.used_percentage or 0)}%{r.R}'
        segs += [five_seg, seven_seg, f'{r.LABEL}plan{r.R}']

    # responsive: drop segments right-to-left until it fits; truncate loc last
    while len(segs) > 1 and _visible_width(SEP.join(segs)) > width:
        segs.pop()
    line = SEP.join(segs)
    if _visible_width(line) > width:
        line = _middle_ellipsis(line, width)
    return [line]


def render(session_info: dict, width: int, *, bg_shift: str = 'warm', theme: Theme | None = None) -> str:
    if width < MIN_WIDTH:
        return ''
    session = SessionInfo.from_dict(session_info)
    r       = Renderer(bg_shift=bg_shift, theme=theme)
    return '\n'.join(render_lines(session, width, r))


def prune_output_dir(out_dir: Path, keep: int = 50) -> None:
    """Keep only the `keep` most recent statusline payloads (by mtime) so the
    directory can't grow unbounded. Count-based (not age-based) so an idle
    session still retains recent history for mon.py. Best-effort."""
    try:
        snaps = sorted(out_dir.glob('statusline.*.json'),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for stale in snaps[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def main() -> None:
    bg_shift   = 'warm'
    theme_name: str | None = None
    args = sys.argv[1:]
    while args:
        a = args.pop(0)
        if a == '--bg-shift' and args:
            v = args.pop(0).lower()
            if v in ('warm', 'cool'):
                bg_shift = v
        elif a.startswith('--bg-shift='):
            v = a.split('=', 1)[1].lower()
            if v in ('warm', 'cool'):
                bg_shift = v
        elif a == '--theme' and args:
            theme_name = args.pop(0)
        elif a.startswith('--theme='):
            theme_name = a.split('=', 1)[1]

    info  = json.loads(sys.stdin.read())
    theme = resolve_theme(theme_name)

    # Write payload so the multi-session observer can index it.
    try:
        out_dir = HOME / '.claude' / 'statusline-output'
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f'statusline.{int(time.time())}.json').write_text(json.dumps(info))
        prune_output_dir(out_dir)
    except OSError:
        pass

    raw_tw = terminal_width()
    if raw_tw < MIN_WIDTH:
        return
    # Fill the terminal: render to the full width (less a small margin) instead
    # of capping at MAX_WIDTH. The single line scales cleanly to any width —
    # segments are dropped right-to-left when space runs short.
    width = max(MIN_WIDTH, raw_tw - 6)

    sys.stdout.write(render(info, width, bg_shift=bg_shift, theme=theme))


if __name__ == '__main__':
    main()
