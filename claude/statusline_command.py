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
    return _osascript_width() or MAX_WIDTH


def _osascript_width() -> int:
    """macOS fallback: ask the frontmost terminal app for its column count via
    AppleScript, cached briefly so osascript isn't spawned on every render.

    Claude Code runs the status line as a subprocess with no controlling TTY and
    COLUMNS unset, so every detector above fails — without this the bar would be
    stuck at the MAX_WIDTH fallback no matter how wide the real window is.
    """
    cache = HOME / '.claude' / '.statusline-width'
    stale: int | None = None
    try:
        val = int(cache.read_text().strip())
        if time.time() - cache.stat().st_mtime < 5.0:
            return val           # fresh cache — skip osascript
        stale = val              # keep as a fallback if osascript fails
    except (OSError, ValueError):
        pass
    if sys.platform == 'darwin':
        for script in (
            'tell application "iTerm2" to tell current session of current window to get columns',
            'tell application "Terminal" to get number of columns of front window',
        ):
            try:
                out = subprocess.run(['osascript', '-e', script],
                                     capture_output=True, text=True, timeout=1)
                w = int(out.stdout.strip())
            except (OSError, ValueError, subprocess.SubprocessError):
                continue
            if w > 0:
                try:
                    cache.write_text(str(w))
                except OSError:
                    pass
                return w
    return stale or 0

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
    def effective_tokens(model: Model, usage: TranscriptUsage) -> float:
        """Billing-weighted session token total, in input-token-equivalents.

        Each class is scaled by its price relative to the input rate — cache
        read 0.1x, cache write 1.25x, output rate_out/rate_in — so re-read cache
        tokens (cheap, and counted every turn) stop dominating the figure. This
        is exactly `session_cost` divided by the input rate, so it tracks the
        billed dollars while staying in token units."""
        rate_in, rate_out = TokenAccounting.rates_for(
            model.display_name or model.id
        )
        if rate_in <= 0:
            return 0.0
        return (
            usage.input_tokens
            + usage.cache_creation_input_tokens * 1.25
            + usage.cache_read_input_tokens * 0.1
            + usage.output_tokens * (rate_out / rate_in)
        )

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

    def is_live(self) -> bool:
        """True when this payload actually carries rate-limit data — the signal
        that the session is on a subscription plan (5h/7d windows) rather than
        API billing."""
        return bool(self.five_hour.resets_at or self.seven_day.resets_at
                    or self.five_hour.used_percentage or self.seven_day.used_percentage)


class BillingCache:
    """Plan vs API billing is inferred from whether a payload carries
    `rate_limits`. Claude Code intermittently emits a frame with `rate_limits`
    null (e.g. a refresh that fires before the window data is fetched), which
    momentarily flips a plan user to `api`. Remember the last live buckets per
    session and reuse them across these gaps so the mode — and the displayed
    countdown/percentages — stay stable. A genuine API session never carries
    rate-limit data, so nothing is ever cached and it correctly stays `api`."""
    TTL  = 1800.0   # seconds; an active plan session refreshes this every render

    @classmethod
    def resolve(cls, session_id: str, rl: RateLimits) -> RateLimits:
        """Return `rl` when it carries data (and persist it); otherwise fall back
        to cached buckets so a null frame doesn't flip the billing mode. This
        covers two gaps: a transient null refresh mid-session, AND a brand-new
        session whose very first frame arrives before window data is fetched —
        the latter has no row of its own yet, so it borrows the most recent live
        row from any session. The 5h/7d windows are account-global, so another
        recent session's buckets are accurate. A genuine API account never writes
        a row at all, so it correctly stays `api`."""
        if not session_id:
            return rl
        # Computed at call time (not a class attribute) so tests monkeypatching
        # HOME — and any future relocation — are honoured.
        path = HOME / '.claude' / '.statusline-billing'
        now = time.time()
        others: list[str] = []                # still-fresh rows for other sessions
        cached: list[str] | None = None       # this session's own row
        best_other: list[str] | None = None   # most-recent live row from any other session
        try:
            for ln in path.read_text().splitlines():
                p = ln.split()
                if len(p) != 6:
                    continue
                try:
                    ts = float(p[0])
                except ValueError:
                    continue
                if now - ts > cls.TTL:
                    continue
                if p[1] == session_id:
                    cached = p
                else:
                    others.append(ln)
                    if best_other is None or ts > float(best_other[0]):
                        best_other = p
        except OSError:
            pass

        if rl.is_live():
            fh, sd = rl.five_hour, rl.seven_day
            others.append(f'{now:.0f} {session_id} {fh.used_percentage} '
                          f'{fh.resets_at} {sd.used_percentage} {sd.resets_at}')
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('\n'.join(others) + '\n')
            except OSError:
                pass
            return rl

        # Prefer this session's own remembered buckets; fall back to the most
        # recent live row from another session for a just-started plan session.
        row = cached or best_other
        if row:
            try:
                return RateLimits(
                    five_hour = RateBucket(used_percentage=float(row[2]), resets_at=int(row[3])),
                    seven_day = RateBucket(used_percentage=float(row[4]), resets_at=int(row[5])),
                )
            except ValueError:
                pass
        return rl


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
    ahead: int = 0
    behind: int = 0
    has_upstream: bool = False
    detached: bool = False

    @classmethod
    def from_cwd(cls, cwd: str) -> GitInfo:
        repo, gitdir   = cls._find_repo(cwd)
        branch, commit = cls._read_head(gitdir)
        detached = branch.startswith('d:')
        if detached:
            branch = branch[2:]   # show the short sha as the "branch"
        modified = untracked = deleted = renamed = ahead = behind = 0
        has_upstream = False
        if branch:
            (modified, untracked, deleted, renamed,
             ahead, behind, has_upstream) = cls._status(repo)
        return cls(
            branch=branch, commit=commit,
            modified=modified, untracked=untracked, deleted=deleted, renamed=renamed,
            ahead=ahead, behind=behind, has_upstream=has_upstream, detached=detached,
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
    def _status(repo: str) -> tuple[int, int, int, int, int, int, bool]:
        modified = untracked = deleted = renamed = ahead = behind = 0
        has_upstream = False
        none = (modified, untracked, deleted, renamed, ahead, behind, has_upstream)
        if not repo:
            return none
        try:
            r = subprocess.run(
                ['git', '-C', repo, 'status', '--porcelain=v1', '-b', '-z',
                 '--untracked-files=normal'],
                capture_output=True, text=True, timeout=2,
            )
        except Exception:
            return none
        entries = [e for e in r.stdout.split('\0') if e]
        i = 0
        if entries and entries[0].startswith('##'):
            header = entries[0]                 # '## main...origin/main [ahead 1, behind 2]'
            has_upstream = '...' in header
            m = re.search(r'ahead (\d+)', header)
            ahead = int(m.group(1)) if m else 0
            m = re.search(r'behind (\d+)', header)
            behind = int(m.group(1)) if m else 0
            i = 1
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
        return modified, untracked, deleted, renamed, ahead, behind, has_upstream


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


def _session_start(transcript_path: str) -> float | None:
    """Epoch of the first timestamped transcript entry (≈ when the session began)."""
    if not transcript_path:
        return None
    p = Path(transcript_path)
    if not p.is_file():
        return None
    try:
        with p.open(errors='ignore') as fh:
            for ln in fh:
                if '"timestamp"' not in ln:
                    continue
                try:
                    ts = json.loads(ln).get('timestamp')
                except (ValueError, TypeError):
                    continue
                if ts:
                    try:
                        return datetime.fromisoformat(str(ts).replace('Z', '+00:00')).timestamp()
                    except ValueError:
                        return None
    except OSError:
        pass
    return None


def render_lines(session: SessionInfo, width: int, r: Renderer) -> list[str]:
    """Single borderless line of ` · `-separated segments. Low-value segments drop
    first when the line exceeds `width`; the full path is truncated only after that
    (keeping git/ctx/model); the model is pinned last.

        <min-path> · git <branch>/<commit> +U ~M -D ↑ahead ↓behind ✓
          · ctx % used/size · tok <billed-weighted> · cache N · <rate>/m
          · T-H:MM 5h% · 7d % · plan          (subscription)
          · cost $<session-cost> · api         (API billing — replaces 5h/7d;
                                                 spend colour: green<50 yellow<100 red)
          · start <opened> · last <refresh> · <model> <effort>

    The path is always shown minimized (intermediate dirs → first letter,
    project name full); it middle-ellipsizes only if even that overflows.

    The `git` label is coloured by state: green clean+synced, yellow pending
    (uncommitted changes or commits to push), red drift/error (behind, diverged,
    or detached HEAD). `✓` shows when the branch is clean, tracking, and synced.
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
    rate_limits = BillingCache.resolve(session.session_id, session.rate_limits)
    five, seven = rate_limits.five_hour, rate_limits.seven_day

    # Minimized home-relative path: intermediate dirs collapse to their first
    # letter, the project name stays full (`short_pwd`). Always minimized so the
    # segments keep horizontal room; the responsive fit below still
    # middle-ellipsizes if even this compact form overflows.
    path_full = f'{r.PWD}{session.short_pwd}{r.R}'

    # git segment: state-coloured `git` label + branch/commit + markers
    git_seg = None
    if git.branch:
        if git.detached or git.behind > 0:
            st = r.alert                                       # red: error / drift
        elif git.untracked or git.modified or git.deleted or git.renamed or git.ahead:
            st = r.warn                                        # yellow: pending
        else:
            st = r.safe                                        # green: clean & synced
        g = f'{st}git{r.R} {r.BRANCH}{git.branch}{r.R}'
        if git.commit:
            g += f'{r.COMMIT}/{git.commit}{r.R}'
        if git.untracked: g += f' {r.DIRTY}+{git.untracked}{r.R}'
        if git.modified:  g += f' {r.DIRTY}~{git.modified}{r.R}'
        if git.deleted:   g += f' {r.DIRTY}-{git.deleted}{r.R}'
        if git.renamed:   g += f' {r.DIRTY}R{git.renamed}{r.R}'
        if git.ahead:     g += f' {r.warn}↑{git.ahead}{r.R}'
        if git.behind:    g += f' {r.alert}↓{git.behind}{r.R}'
        clean = not (git.untracked or git.modified or git.deleted
                     or git.renamed or git.ahead or git.behind)
        if clean and git.has_upstream and not git.detached:
            g += f' {r.safe}✓{r.R}'
        git_seg = g

    model = f'{r.model_colour(session.model_name)}{session.model_name}{r.R}'
    if session.model_thinking:
        model += f' {r.MODEL}{ITALIC}{session.model_thinking}{r.R}'

    # Context %: prefer the payload's `used_percentage` — the same field Claude
    # Code derives its own context indicator from (the right-side context-low
    # warning) — so our number never disagrees with it. Fall back to raw
    # total/size only when an older Claude Code payload omits the field.
    ctx_pct = (float(ctx.used_percentage) if ctx.used_percentage is not None
               else ((total / size * 100) if size else 0.0))
    ctx_clr = r.fill_colour(total / SOFT_LIMIT * 100)
    ctx_seg = (f'{r.LABEL}ctx {ctx_clr}{ctx_pct:.0f}%{r.R} '
               f'{r.CTX}{fmt_tok(total)}{r.LABEL}/{fmt_tok(size)}{r.R}')
    cache_seg = f'{r.LABEL}cache {r.TOK_DIM}{fmt_tok(usage.cache_read)}{r.R}'
    rate_seg  = f'{r.TOK_ICON}{fmt_tok(tok_rate)}{r.R}{r.LABEL}/m{r.R}'
    # billing-weighted session token total, in input-token-equivalents: each
    # class scaled by its price (cache read 0.1x, cache write 1.25x, output 5x),
    # so re-read cache tokens don't dominate. Tracks the billed cost in token units.
    eff_tok   = TokenAccounting.effective_tokens(session.model, usage)
    total_seg = f'{r.LABEL}tok {r.TOK}{fmt_tok(round(eff_tok))}{r.R}'

    # Segments after the path, each (text, drop_priority). Priorities 1–3 are kept
    # (path truncates instead); ≥4 are dropped first (trivia/limits).
    segs: list[tuple[str, int]] = []
    if git_seg:
        segs.append((git_seg, 1))
    segs.append((ctx_seg, 2))
    segs.append((total_seg, 4))
    segs.append((cache_seg, 8))
    segs.append((rate_seg, 9))
    # Billing mode. Subscription plans report 5h/7d rate-limit windows; API
    # billing does not. When on a plan, show the limit windows + a `plan` tag.
    # When on API, those windows are meaningless — replace them with the
    # estimated session cost and tag it `api` so the mode is unambiguous.
    on_plan = rate_limits.is_live()
    if on_plan:
        reset    = _fmt_reset(five.resets_at)
        five_pct = f'{r.fill_colour(float(five.used_percentage or 0))}{int(five.used_percentage or 0)}%{r.R}'
        # Lead with the countdown (T-H:MM) — the time-to-refresh is the signal;
        # the `5h` label is only needed when there's no countdown to imply it.
        if reset:
            five_seg = f'{r.COMMIT}{reset}{r.R} {five_pct}'
        else:
            five_seg = f'{r.LABEL}5h {five_pct}'
        seven_seg = f'{r.LABEL}7d {r.fill_colour(float(seven.used_percentage or 0))}{int(seven.used_percentage or 0)}%{r.R}'
        segs += [(five_seg, 4), (seven_seg, 5), (f'{r.LABEL}plan{r.R}', 6)]
    else:
        cost = effective_session_cost(session, usage)
        # Reactive spend colour: green ≤ $49, yellow $50–99, red ≥ $100.
        cost_clr = r.safe if cost < 50 else (r.warn if cost < 100 else r.alert)
        segs += [(f'{r.LABEL}cost {cost_clr}${cost:.2f}{r.R}', 5),
                 (f'{r.LABEL}api{r.R}', 6)]
    now_str = datetime.now().strftime('%H:%M')
    start   = _session_start(session.transcript_path)
    if start:
        started = datetime.fromtimestamp(start).strftime('%d-%b-%y %H:%M').lower()
        segs.append((f'{r.LABEL}start {r.white_brt}{started}{r.R}{SEP}'
                     f'{r.LABEL}last {r.white_brt}{now_str}{r.R}', 7))   # opened date+time · last refresh
    else:
        segs.append((f'{r.LABEL}last {r.white_brt}{now_str}{r.R}', 7))
    segs.append((model, 3))   # pinned visually last

    # ---- responsive fit ----
    # The path is the primary elastic: it shrinks (smart middle-ellipsis) to free
    # space and KEEP segments. Segments are only dropped (lowest value first) once
    # the path is already at its floor and the line still overflows.
    PATH_FLOOR = 14
    full_pw = _visible_width(path_full)

    def seg_block(ss: list) -> int:
        # width of the segments + the separator that joins them to the path
        return _visible_width(SEP.join(t for t, _ in ss)) + (_visible_width(SEP) if ss else 0)

    while True:
        budget = width - seg_block(segs)
        if budget >= full_pw or budget >= PATH_FLOOR:
            break                       # path fits in full, or can show >= floor
        cand = [(p, i) for i, (_, p) in enumerate(segs) if p >= 1]
        if not cand:
            break
        segs.pop(max(cand)[1])          # drop the lowest-value segment, freeing path room

    budget    = width - seg_block(segs)
    path_disp = path_full if full_pw <= budget else _middle_ellipsis(path_full, max(3, budget))
    line = SEP.join([path_disp] + [t for t, _ in segs])
    if _visible_width(line) > width:    # final safety
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
