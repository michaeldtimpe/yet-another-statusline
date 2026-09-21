---
name: tmck-code-statusline
description: Edit the Claude Code statusline renderer safely. Use when touching claude/statusline_command.py, claude/statusline/*.py, claude/mon*, or related tests. Covers the flat single-line segment renderer (render_lines' drop-priority fit logic), the payload `from_dict` parsers, TokenAccounting pricing, theme colour slots, Monaco-safety (no Nerd Font/PUA glyphs), and the pytest + one-frame-render check.

---

# Statusline

`claude/statusline_command.py` (~1450 lines) renders one flat, borderless,
` · `-separated line — no box, no gradient, no pill. Most bugs here are
silent: a dropped segment, a wrong colour threshold, a width miscount that
only shows up at one terminal size. This skill exists to make those bugs loud.

## Architecture map

- **Module helpers**: `_atomic_write`, `terminal_width`, `_osascript_width`,
  `_visible_width`, `_middle_ellipsis`.
- **`TokenAccounting`**: static `rates_for`, `cache_read_mult`, `session_cost`,
  `effective_tokens`, `day_cost`. All rate/cost math lives here — never inline
  a price multiplier elsewhere.
- **Payload parsers**: `Model`, `Effort`, `Thinking`, `CurrentUsage`,
  `RateBucket`, `Workspace`, `Cost`, `ContextWindow`, `RateLimits`,
  `SessionInfo` — each exposes `from_dict`.
- **`BillingCache`**: sticky plan-vs-API detection across `null` `rate_limits`
  frames (Claude Code sometimes omits the field even on a subscription).
- **`TokenLog` / `TokenRate`**: shared state under `~/.claude/`, written only
  via `_atomic_write` (concurrent sessions read-modify-write these files).
- **`GitInfo`**: reads `.git` directly (including worktrees/packed-refs) plus
  one `git status` subprocess.
- **`TranscriptUsage`**: sums usage from the session transcript jsonl,
  deduplicated by message id.
- **`Renderer`**: theme colour slots only — `_apply_theme`, `model_colour`,
  `fill_colour`. No layout, no border, no gradient math.
- **`render_lines(session, width, r, record=True)`**: builds `(text,
  drop_priority)` segments, then a fit loop drops the highest-priority-number
  (lowest-value) segment first until the path can render at or above its
  floor width, middle-ellipsizing the path only after that.
- **`render(session_info, width, *, bg_shift, theme, record=True)`**: the
  public entry point. `record=False` is a read-only render (no log write, no
  rate sample, no billing-cache write) — used by `mon.py` to replay stored
  payloads.
- **`write_payload_snapshot`**: writes one `statusline.<session_id>.json` per
  session under `~/.claude/statusline-output/` (overwritten in place, pruned
  to the most recent 50 by `prune_output_dir`).
- **`main`**: reads stdin JSON, writes the payload snapshot, resolves width
  and theme, prints the rendered line.

**Where to make a change:**

- New segment → add to the `segs: list[tuple[str, int]]` in `render_lines`
  with a drop priority (higher number = dropped first; git/ctx/model currently
  sit at priorities 1–3).
- New/changed colour → a slot on `Theme` in `claude/statusline/themes.py`,
  wired through `Renderer._apply_theme`.
- New payload field → the matching class's `from_dict`.
- Pricing/rate change → `TokenAccounting` only (see `rates_for`,
  `cache_read_mult`); never inline `1.25`/`0.1`/etc. elsewhere.

## Invariants

- **Never use `len()` for column math.** Use `_visible_width` — it strips ANSI
  escapes and counts wide chars as 2.
- **Output must stay Monaco-safe**: no Nerd Font / Private Use Area glyphs, no
  Symbols-for-Legacy-Computing. Enforced by `test/test_monaco_safe.py`. Quick
  manual check on any file:
  ```bash
  python3 -c "
  import sys
  for ln, line in enumerate(open(sys.argv[1]), 1):
      for c in line:
          cp = ord(c)
          if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD or 0x1FB00 <= cp <= 0x1FBFF:
              print(f'{sys.argv[1]}:{ln}  U+{cp:05X}  {c!r}')
  " claude/statusline_command.py
  ```
  As of this writing the scan is clean (no PUA/legacy-computing glyphs in
  source). If your change introduces one — e.g. copying an icon back in from
  the upstream fork — don't: this renderer is text-label-only by design. If
  you must carry a raw non-ASCII glyph through an edit, hoist it to a named
  module-level constant first so `Edit`/diff/chat round-trips don't lose or
  mangle the bytes.
- **The statusline must never raise.** Every file read, subprocess call, and
  AppleScript probe is best-effort with a timeout/try-except; a malformed or
  missing input should degrade (skip a segment, fall back to an estimate),
  never crash.
- **Shared state files are written only through `_atomic_write`.** `TokenLog`,
  `TokenRate`, `BillingCache`, and `write_payload_snapshot` all go through it
  because multiple sessions can read-modify-write the same file concurrently.
- **`render(..., record=False)` must stay side-effect free.** `mon.py` calls
  it every ~2s to replay stored payloads; it must not touch `TokenLog`,
  `TokenRate`, or `BillingCache` state.
- Canonical field vocabulary (what `tkn`, `ctx`, `cch`, etc. mean and where
  the numbers come from) lives in `CONTEXT.md` at repo root — read it before
  renaming or reinterpreting a displayed term, and update it in the same
  change if a term's meaning or source field changes.

## Pre-edit checklist

1. Read `CONTEXT.md` for the canonical field glossary.
2. Baseline tests: `uv run pytest -q`. Note the pass count.
3. Baseline one-frame render:
   ```bash
   python3 claude/statusline_command.py < claude/statusline/session-info-example.json
   ```
   Confirms the renderer runs end-to-end before you touch it.

## Post-edit checklist

1. `uv run pytest -q` — must be green, pass count matches baseline plus any
   tests you added.
2. Re-run the one-frame render above and `make demo` (animated preview in a
   hermetic temp environment) — eyeball that segments still make sense and
   nothing crashed or produced tofu/garbled glyphs.
3. Any behaviour change needs a test added or updated. Put new tests in the
   file matching what changed (e.g. `test_token_rate.py`,
   `test_git_info.py`, `test_render_callable.py`, `test_mon_layout.py`).
4. If a displayed term's meaning or source field changed, update the glossary
   in `CONTEXT.md` in the same change.

## Multi-session observer

`claude/mon.py` aggregates every active session's statusline into a single
alternate-screen TUI. It imports the public `render(session_info, width, *,
bg_shift, theme, record=False)` callable from `statusline_command.py`,
calling it with `record=False` since it's replaying stored payloads, not
producing a live frame. The supporting package `claude/mon/` has:
`discovery.py` (finds active sessions via `~/.claude/projects/*/*.jsonl`
mtimes and reads the one-per-session payload files under
`~/.claude/statusline-output/statusline.<session_id>.json`), `lifecycle.py`
(classifies sessions bright/dim/removed, applies SGR-faint dimming),
`layout.py` (header/footer formatting, empty/narrow body stubs, overflow
clipping, rate-limit/cost aggregation), and `tui.py` (alt-screen entry/exit,
`RefreshClock`, SIGWINCH handling, CLI arg parsing). `make mon/run` launches
it locally; `make mon/install` symlinks it into `~/.claude/`.

## Sibling skills

`python-style` and `pytest-style` apply as usual when touching `.py` files.
This skill adds the statusline-specific rules on top.
