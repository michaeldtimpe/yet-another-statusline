STATUSLINE_SRC := $(CURDIR)/claude/statusline_command.py
STATUSLINE_SH  := $(CURDIR)/claude/statusline-command.sh
THEMES_SRC     := $(CURDIR)/claude/statusline/themes.py
MON_SRC        := $(CURDIR)/claude/mon.py
INSTALL_DIRS   := $(HOME)/.claude $(HOME)/.claude.personal

install:
	@for dir in $(INSTALL_DIRS); do \
		mkdir -p "$$dir/statusline"; \
		ln -sf $(STATUSLINE_SRC) "$$dir/statusline-command.py"; \
		ln -sf $(STATUSLINE_SRC) "$$dir/statusline_command.py"; \
		ln -sf $(STATUSLINE_SH)  "$$dir/statusline-command.sh"; \
		ln -sf $(THEMES_SRC)     "$$dir/statusline/themes.py"; \
		echo "installed -> $$dir"; \
	done

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

.PHONY: install demo demo/img mon/install mon/run
