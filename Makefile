STATUSLINE_SRC := $(CURDIR)/claude/statusline_command.py
THEMES_SRC     := $(CURDIR)/claude/statusline/themes.py
MON_SRC        := $(CURDIR)/claude/mon.py
INSTALL_DIR	   := $(HOME)/.claude

install:
	@mkdir -p "$(INSTALL_DIR)/statusline"
	@ln -sf $(STATUSLINE_SRC) "$(INSTALL_DIR)/statusline_command.py" || true
	@ln -sf $(THEMES_SRC)     "$(INSTALL_DIR)/statusline/themes.py" || true
	@echo "installed -> $(INSTALL_DIR)/statusline_command.py"
	@echo "installed -> $(INSTALL_DIR)/statusline/themes.py"

# One-command setup for a fresh machine: symlink, register in settings.json,
# pick a theme. Override the theme with `THEME=claude-dark make deploy`.
deploy: install
	@python3 claude/register_statusline.py
	@printf '%s\n' "$${THEME:-llmtop}" > "$(INSTALL_DIR)/statusline-theme"
	@echo "theme       -> $${THEME:-llmtop}  ($(INSTALL_DIR)/statusline-theme)"
	@echo ""
	@echo "Done. Claude Code shows the statusline on its next render."
	@echo "  - Font: any monospace works (Monaco included); no Nerd Font required."
	@echo "  - Keep this clone in place (the install symlinks back to it)."
	@echo "  - Themes: claude-dark | claude-light | catppuccin-latte | catppuccin-mocha | llmtop"

demo:
	@python3 claude/statusline/demo.py

demo/img:
	@python3 claude/statusline/demo.py --snapshots demo/

mon/install:
	@for dir in $(INSTALL_DIRS); do \
		if ! test -d "$$dir"; then \
			echo "directory $$dir does not exist, skipping"; \
			continue; \
		fi; \
		ln -sf $(MON_SRC) "$$dir/mon.py"; \
		echo "installed mon -> $$dir"; \
	done

mon/run:
	uv run python claude/mon.py

.PHONY: install deploy demo demo/img mon/install mon/run
