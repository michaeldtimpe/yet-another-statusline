# YAS! (Yet Another Statusline)

> [!IMPORTANT]
> _The statusline requires a ["Nerd font"](https://www.nerdfonts.com/font-downloads) in order to display the icons_

To install, run:

```bash
make install
```

## Themes

Pick a theme in priority order: `--theme=<name>` flag → `CLAUDE_STATUSLINE_THEME`
env var → `~/.claude/statusline-theme` file (contains just the name) → default
(`claude-dark`).

Available: `claude-dark`, `claude-light`, `catppuccin-latte`, `catppuccin-mocha`,
`llmtop`. The `llmtop` theme is light-background and draws from the terminal's own
ANSI palette (indices 0–15), so it tracks your iTerm2/terminal profile colours.

```bash
echo llmtop > ~/.claude/statusline-theme   # persist a selection
```

## Demo

<img width="1264" height="552" alt="statusline-demo" src="https://github.com/user-attachments/assets/64e941b8-90a4-4ec8-98e0-973a57c04212" />


## Layout Reference

<img width="1723" height="688" alt="image" src="https://github.com/user-attachments/assets/03c65cb2-f533-4194-94df-416d9b7e820e" />

---

## Commands

To demo/test:

```bash
make demo
```
