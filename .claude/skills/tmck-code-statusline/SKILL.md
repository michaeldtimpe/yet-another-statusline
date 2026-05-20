---
name: tmck-code-statusline
description: Edit the Claude Code statusline renderer safely. Use when touching claude/statusline-command.py, claude/statusline/*.py, claude/statusline-command.sh, or related tests. Covers Nerd Font PUA glyph hazards, border/elbow column math, and the demo-based visual check.
---

# Statusline

The statusline renderer is a single-pass terminal painter with hand-tuned column math. Most bugs here are silent — wrong by one column, invisible icon, dropped byte through an Edit round-trip. This skill exists to make those bugs loud.

## Pre-edit checklist

Run all four before editing:

1. **Read `CONTEXT.md`** at repo root. The terms Billed Input, Cache Read, Output, Day Total, Context Window Size, Compaction-Risk Zone, Five-Hour Limit, Seven-Day Limit are canonical — don't rename or alias them in code without a paired update.
2. **Catalogue PUA glyphs on touched lines.** Run:
   ```bash
   python3 -c "
   import sys
   for ln, line in enumerate(open(sys.argv[1]), 1):
       for c in line:
           cp = ord(c)
           if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD:
               print(f'{sys.argv[1]}:{ln}  U+{cp:05X}  {c!r}')
   " claude/statusline-command.py
   ```
   Any hit on a line you plan to Edit triggers the **PUA refactor rule** below.
3. **Baseline tests**: `uv run pytest -q`. Note pass count.
4. **Baseline demo**: `COLUMNS=160 uv run python claude/statusline/demo.py | head -40`. Note current visual.

## PUA refactor rule (mandatory before editing)

Nerd Font icons in this repo live in the Unicode Private Use Area (U+E000–U+F8FF and U+F0000–U+FFFFD). Literal PUA glyphs in source are invisible in many editors, render as `□` in others, and **get dropped through chat/agent round-trips** — which makes `Edit.old_string` matching fail with a stale-looking "string to replace not found" error.

If a line you need to Edit contains a raw PUA glyph, **hoist the glyph to a named module-level constant first**, then Edit. No exceptions.

Convention:

```python
# Nerd Font Private Use Area glyphs. Encoded as escapes so Edit, diff, and
# chat round-trips never lose the bytes. Render only in a Nerd-Font-capable
# terminal.
ICON_MODEL_BADGE = '\uf4cd'      # nf-fa cube         (model row)
ICON_THINKING    = '\U000f1a53'  # nf-md brain        (thinking indicator)
ICON_PATH        = '\uef85'      # nf-cod folder      (path row)
# ... etc, one per glyph
```

Reference the constant in f-strings: `f'{model_clr}{ICON_MODEL_BADGE}  {model_name}...'`.

Runtime cost is **zero** — `'\uf4cd'` (in source) and the literal glyph compile to the identical `str` object; CPython interns and the `.pyc` cache eliminates parse cost after first load.

### Fallback when refactor isn't feasible mid-task

If the line has a PUA glyph and you genuinely can't refactor first (e.g., user is mid-edit and asked for one surgical change), use a Bash heredoc with `python3` that reads, `str.replace`s, and writes. Python preserves the bytes exactly:

```bash
python3 << 'PY'
path = 'claude/statusline-command.py'
with open(path) as f:
    s = f.read()
old = "...exact old text with raw glyph copied through Read...\n"
new = "...replacement...\n"
assert old in s, 'old not found'
with open(path, 'w') as f:
    f.write(s.replace(old, new, 1))
PY
```

This works because `Read` preserves the bytes when it loads them into your context, even when subsequent `Edit` calls can't transmit them through `old_string`.

## Rendering invariants (silent-bug cheat-sheet)

These are the things pytest won't catch — get them wrong and the box draws crooked.

### Width math

- **Never** use `len()` for column math. Use `_visible_width` — it strips ANSI escapes via `_ANSI_RE` and counts wide chars (BMP emoji `0x1F300–0x1FAFF`) as 2.
- Nerd Font PUA chars count as width 1. Correct in a Nerd-Font terminal; would be wrong elsewhere, but elsewhere isn't supported.

### Column indexing

- `border_top(downs=...)`, `border_separator_dim(ups=..., downs=...)`, `border_separator(ups=...)`, `border_bottom(ups=...)` take **1-indexed visual positions** of the inline `│` they should attach an elbow to.
- `border_line(content, width)` wraps content as `│ <content>...│`. Content starts at visual column 2, which is **col-form 3** (1-indexed).

### vsep convention

The vertical divider inside a content row is the 5-char string `'  │  '` (two spaces, pipe, two spaces). The `│` sits at vsep-index 2.

```python
vsep = f'  {self.BORDER}│{self.R}  '   # visible width 5; │ at offset 2
```

### Section helpers that participate in dividers return `(line, div_offset)`

When a section contributes a `│` that should grow elbows on the surrounding borders, the helper returns `(line, div_offset)` where `div_offset` is the **0-indexed visible position of the `│` inside `line`**. Examples: `path_model_row`, `model_section`.

Caller converts to a border col:
```python
# Standalone row:
model_div_col = 3 + model_div_offset

# Inside a combined row whose own divider sits at top_div_col:
model_div_col = top_div_col + 3 + model_div_offset
```

Then thread `model_div_col` into the surrounding `border_top(downs=...)` (only if the row is directly under the top border) and the next `border_separator_*(ups=...)`.

### Gradient

`grad_at(i, width, fill=...)` returns the ANSI for column `i` of the rainbow border. Don't reorder the `parts` list when extending border helpers — the gradient is positional.

## Post-edit checklist

1. **`uv run pytest -q`** — must be green. The pass count should match the baseline plus any tests you added.
2. **Re-run the demo at multiple widths** — eyeball borders and elbow alignment:
   ```bash
   for w in 60 100 160; do
     echo "--- width=$w ---"
     COLUMNS=$w uv run python claude/statusline/demo.py | head -20
   done
   ```
   Every `┬` in a top border must line up with a `│` in the row beneath it, and a `┴` in the separator below.
3. **Tests** — any behaviour change needs a test added or updated. Use the `strip_ansi` helper from `test/conftest.py`. Width-sensitive assertions go through `_visible_width`.
4. **`CONTEXT.md`** — if any displayed term changed (label, glyph meaning, what a number represents), update the glossary in the same change.

## Sibling skills

`python-style` and `pytest-style` apply as usual when touching `.py` files. This skill adds the statusline-specific rules on top.
