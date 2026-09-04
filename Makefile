.PHONY: start stop install migrate db logs clean
# make's default recipe shell is /bin/sh, which is dash on this platform and rejects
# `wait -n` below ("Illegal option -n"); bash 4.3+ supports it.
SHELL := bash
-include .env
export

BACKEND  := backend/api
FRONTEND := frontend/app
VENV     := $(CURDIR)/.venv
# per-checkout, so two worktrees never share one Postgres volume
COMPOSE_PROJECT_NAME ?= agent-office-$(notdir $(CURDIR))
export COMPOSE_PROJECT_NAME
COMPOSE  := docker compose -f devops/docker-compose.yml

# absolute, and set here rather than in .env: the backend runs with cwd=backend/api,
# so a relative "." would resolve to backend/api.
export AGENT_OFFICE_REPO_ROOT    := $(CURDIR)
export AGENT_OFFICE_RUNTIME_ROOT := $(CURDIR)/.agent-office/runtime
# consumed by backend/api/entrypoint.sh
export ALEMBIC := $(VENV)/bin/alembic
export UVICORN := $(VENV)/bin/uvicorn

# GNU make remakes an out-of-date included file and then restarts itself, so a .env
# created here is loaded before any recipe runs. No prerequisite: this fires only when
# .env is absent, never to compare it against .env.example.
.env:
	@cp .env.example $@ && echo "created .env from .env.example."

install: .env
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -e "$(BACKEND)[dev]"
	npm --prefix $(FRONTEND) install

db: .env
	$(COMPOSE) up -d --wait

# a manual escape hatch; `start` no longer depends on it, the entrypoint migrates
migrate: db
	cd $(BACKEND) && $(ALEMBIC) upgrade head

# explicit PIDs, not `kill 0`; first failure brings the other down and sets the exit code
start: db
	@set -m; \
	sh $(BACKEND)/entrypoint.sh & api=$$!; \
	npm --prefix $(FRONTEND) run dev & web=$$!; \
	trap 'kill $$api $$web 2>/dev/null' INT TERM; \
	wait -n $$api $$web; status=$$?; \
	kill $$api $$web 2>/dev/null; wait $$api $$web 2>/dev/null; \
	exit $$status

# stops the database only; Ctrl-C stops the two servers `start` launched
stop:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f db

# destroys the database volume; stop `make start` first
clean:
	$(COMPOSE) down -v
