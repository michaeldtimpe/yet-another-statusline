# yet-another-statusline

A compact, **single-line, Monaco-safe** status line for
[Claude Code](https://claude.com/claude-code) — **no Nerd Font required**. It
shows your working directory, git state, context usage, plan quotas, and session
timing on one line that adapts to the terminal width.

```
~/Downloads/yet-another-statusline · git main/24b6a4f ✓ · ctx 84% 844.1K/1.0M · cache 157.6M · 18.0K/m · 5h 20% T-1:05 · 7d 32% · plan · up 2h14m (11:00 → 13:14) · Opus 4.7 1M xhigh
```

> Personal fork of [tmck-code/yet-another-statusline](https://github.com/tmck-code/yet-another-statusline),
> rebuilt flat and borderless. The full field glossary lives in
> [CONTEXT.md](CONTEXT.md).

## Requirements

- macOS or Linux
- **Python 3.9+** — standard library only, nothing to `pip install`
- Any monospace terminal font (Monaco, Menlo, SF Mono, …). **No Nerd Font.**

## Install / deploy

```bash
git clone https://github.com/michaeldtimpe/yet-another-statusline.git \
  ~/code/yet-another-statusline
cd ~/code/yet-another-statusline
make deploy
```

`make deploy` does everything:

- symlinks the renderer into `~/.claude/`
- registers it in `~/.claude/settings.json` (a **merge** — it won't clobber your
  existing settings)
- selects a theme (`llmtop` by default; `THEME=claude-dark make deploy` to pick
  another)

Then restart Claude Code (or just wait for the next render). Set your terminal
font to any monospace you like.

> **Keep the clone where you put it** — the install symlinks back to it, so don't
> delete or move the directory.

### Another MacBook

Same three commands (`git clone … && cd … && make deploy`). Nothing machine-
specific is baked in; the theme tracks each terminal's own ANSI palette.

### Updating

```bash
cd ~/code/yet-another-statusline && git pull && make deploy
```

## The line, explained

Segments are separated by ` · `. As the terminal narrows the **path shrinks
first** (smart middle-ellipsis) to keep the data segments; only once the path is
at its floor do the lowest-value segments drop (rate → cache → uptime → …). The
model is pinned last.

| Segment | Meaning |
|---|---|
| `~/path/to/dir` | working directory, home-relative; shown in full, truncated only on overflow |
| `git <branch>/<commit>` | git label, **colored by state**: 🟢 clean & synced · 🟡 pending · 🔴 drift/error |
| `+N ~N -N RN` | untracked · modified · deleted · renamed (only non-zero shown) |
| `↑N ↓N` | commits ahead / behind the upstream |
| `✓` | clean working tree, tracking a remote, fully synced |
| `ctx N% used/size` | context-window occupancy — your compaction-risk gauge |
| `cache N` | cumulative cache-read tokens this session |
| `N/m` | token throughput per minute |
| `5h N% T-H:MM` | rolling 5-hour plan quota + time to reset |
| `7d N%` | rolling weekly plan quota |
| `plan` | you're on a subscription (so cost is notional and not shown) |
| `HH:MM → HH:MM` | session opened → last refresh (the render's clock time) |
| `Opus 4.7 1M xhigh` | model + thinking effort (pinned last) |

The git **state color** is your traffic light: green = clean & in sync,
yellow = uncommitted changes and/or commits to push, red = behind/diverged/
detached. The last-refresh time doubles as a freshness signal — the bar only
re-renders on activity, so a stale time means the session has been idle.

## Terminal width

Claude Code runs the status line as a subprocess with no TTY and `COLUMNS` unset,
so the usual width probes can't see your real window. On macOS the renderer falls
back to asking iTerm2 / Terminal for the column count via AppleScript (cached ~5s,
so it tracks resizes without spawning `osascript` on every render). To force a
width (tmux, SSH, or any non-AppleScript terminal), write it to
`~/.claude/terminal-width`:

```bash
echo 200 > ~/.claude/terminal-width   # overrides detection
```

## Themes

Selection order (first match wins): `--theme=<name>` flag →
`CLAUDE_STATUSLINE_THEME` env var → `~/.claude/statusline-theme` file →
default (`claude-dark`).

Available: `claude-dark`, `claude-light`, `catppuccin-latte`,
`catppuccin-mocha`, `llmtop`. **`llmtop`** is light-background and draws from the
terminal's own ANSI palette (indices 0–15), so it matches your iTerm2/terminal
profile.

```bash
echo llmtop > ~/.claude/statusline-theme   # persist a choice
```

## Development

```bash
uv run pytest -q          # test suite (stdlib renderer; tests use uv + pytest)
make demo                 # animated live preview in a hermetic temp environment
make demo/img             # write per-scenario snapshots to demo/
```

`claude/statusline_command.py` is the whole renderer (`render()` →
`render_lines()`); `claude/statusline/themes.py` holds the themes;
`claude/mon.py` is an optional multi-session observer (`make mon/run`). See
[CONTEXT.md](CONTEXT.md) for the canonical field glossary and rendering notes.

## Credit

Forked from [tmck-code/yet-another-statusline](https://github.com/tmck-code/yet-another-statusline)
(BSD-3-Clause). This fork removes the Nerd Font glyphs, box, gradients, and
sparkline in favor of a flat, single-line, Monaco-safe layout.
