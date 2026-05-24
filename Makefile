STATUSLINE_SRC := $(CURDIR)/claude/statusline_command.py
STATUSLINE_SH  := $(CURDIR)/claude/statusline-command.sh
THEMES_SRC     := $(CURDIR)/claude/statusline/themes.py
INSTALL_DIRS   := $(HOME)/.claude $(HOME)/.claude.personal

statusline/install:
	@for dir in $(INSTALL_DIRS); do \
		mkdir -p "$$dir/statusline"; \
		ln -sf $(STATUSLINE_SRC) "$$dir/statusline-command.py"; \
		ln -sf $(STATUSLINE_SH)  "$$dir/statusline-command.sh"; \
		ln -sf $(THEMES_SRC)     "$$dir/statusline/themes.py"; \
		echo "installed -> $$dir"; \
	done

statusline/test:
	@python3 claude/statusline/demo.py

.PHONY: statusline/install statusline/test
