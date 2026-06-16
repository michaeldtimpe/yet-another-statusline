# yet-another-statusline

A compact, **single-line, Monaco-safe** status line for
[Claude Code](https://claude.com/claude-code) — **no Nerd Font required**. It
shows your working directory, git state, context usage, plan quotas (or API
spend), and session timing on one line that adapts to the terminal width.

```
~/D/yet-another-statusline · git main/90db263 ✓ · ctx 84% 844.1K/1.0M · tok 16.4M · cache 157.6M · 18.0K/m · T-1:05 20% · 7d 32% · plan · start 25-may-26 11:00 · last 13:14 · Opus 4.7 1M xhigh
```

On metered API billing there are no plan quotas, so the `5h/7d/plan` trio is
replaced by the session spend (colored by amount) tagged `api`:

```
~/D/yet-another-statusline · git main/90db263 ✓ · ctx 84% 844.1K/1.0M · tok 16.4M · cache 157.6M · 18.0K/m · cost $42.18 · api · start 25-may-26 11:00 · last 13:14 · Opus 4.7 1M xhigh
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
specific is baked in; the theme tracks each terminal's own ANSI palette. Two
first-run notes: (1) allow the one-time macOS **Automation** prompt so the bar
can read your real terminal width (see [Terminal width](#terminal-width)); (2)
keep the clone where you cloned it — the install symlinks back to it, so a later
`git pull` alone picks up renderer updates (re-run `make deploy` only to change
the theme or re-register settings).

### Updating

```bash
cd ~/code/yet-another-statusline && git pull && make deploy
```

## The line, explained

Segments are separated by ` · `. The **path is always minimized** (intermediate
directories collapse to their first letter, the project name stays full) so the
data segments keep horizontal room. As the terminal narrows the path shrinks
further (smart middle-ellipsis); only once the path is at its floor do the
lowest-value segments drop (rate → cache → timestamp → plan/quota → tok). `git`,
`ctx`, and the model are protected, and the model is pinned last.

| Segment | Meaning |
|---|---|
| `~/p/to/dir` | working directory, home-relative, **minimized** (intermediate dirs → first letter, project name kept full); middle-ellipsized further only on overflow |
| `git <branch>/<commit>` | git label, **colored by state**: 🟢 clean & synced · 🟡 pending · 🔴 drift/error |
| `+N ~N -N RN` | untracked · modified · deleted · renamed (only non-zero shown) |
| `↑N ↓N` | commits ahead / behind the upstream |
| `✓` | clean working tree, tracking a remote, fully synced |
| `ctx N% used/size` | context-window occupancy (compaction risk); the `%` is Claude Code's own `used_percentage`, so it matches the context warning Claude Code shows on the right of this row |
| `tok N` | session tokens, **billing-weighted** (cache read 0.1×, cache write 1.25×, output 5×) and in input-token-equivalents, so repeated cache re-reads don't dominate; tracks billed cost in token units |
| `cache N` | cumulative cache-read tokens this session (raw count — much larger than `tok` because re-reads are counted every turn) |
| `N/m` | token throughput per minute |
| `T-H:MM N%` | rolling 5-hour plan quota: time to reset (countdown leads) + % used (subscription only) |
| `7d N%` | rolling weekly plan quota (subscription only) |
| `plan` | you're on a subscription (so cost is notional and not shown) |
| `cost $N` | **API billing only** — session spend, replacing the `5h/7d/plan` trio; colored 🟢 under $50 · 🟡 $50–99 · 🔴 $100+ |
| `api` | you're on metered API/console billing (so `cost` is real spend) |
| `start DD-mon-YY HH:MM · last HH:MM` | session opened (date + clock time) and last refresh (this render's clock time) |
| `Opus 4.7 1M xhigh` | model + thinking effort (pinned last) |

The git **state color** is your traffic light: green = clean & in sync,
yellow = uncommitted changes and/or commits to push, red = behind/diverged/
detached. The `last` time doubles as a freshness signal — the bar only
re-renders on activity, so a stale time means the session has been idle.

> **No duplicate context %.** When you're near the limit, Claude Code shows its
> own *"N% context used"* warning on the right side of this same row — that's
> Claude Code's notification area, not part of this statusline and not removable
> from a script. The `ctx` segment reads the same `used_percentage` field, so the
> two agree instead of showing two different numbers.

## Terminal width

Claude Code runs the status line as a subprocess with no TTY and `COLUMNS` unset,
so the usual width probes can't see your real window. On macOS the renderer falls
back to asking **iTerm2 / Terminal.app** for the column count via AppleScript
(cached ~5s, so it tracks resizes without spawning `osascript` on every render).

> **First run on a new Mac:** the first AppleScript call triggers a one-time
> macOS **Automation** permission prompt (*"… wants to control iTerm2"*) — allow
> it, or the bar stays at the 160-column fallback until you do.

To force a width (tmux, SSH, or any terminal that isn't iTerm2/Terminal.app),
write it to `~/.claude/terminal-width`:

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
