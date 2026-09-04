#!/usr/bin/env sh
# Migrations run here, not in the Makefile, so they happen whenever the backend
# starts -- including a direct ./backend/api/entrypoint.sh, not only `make start`.
set -eu
cd "$(dirname "$0")"

# Relative to this script's own directory (see the `cd` above), matching Makefile's
# VENV := $(CURDIR)/.venv. `make start` overrides both with absolute paths, so its
# behaviour is unchanged; this fallback only matters for a direct invocation.
VENV_BIN="../../.venv/bin"
ALEMBIC="${ALEMBIC:-$VENV_BIN/alembic}"
UVICORN="${UVICORN:-$VENV_BIN/uvicorn}"

run_entrypoint() {
    require_executable "$ALEMBIC" ALEMBIC
    require_executable "$UVICORN" UVICORN
    migrate_to_head
    exec "$UVICORN" app:app --port 8000 "$@"
}

require_executable() {
    [ -x "$1" ] && return 0
    echo "$2 not found or not executable at '$1'. Run \`make install\`, or export $2 to override it." >&2
    exit 1
}

migrate_to_head() {
    set +e
    probe="$(read_current_revision_output)"
    probe_rc=$?
    set -e
    refuse_unknown_revision "$probe" "$probe_rc"
    echo "[entrypoint] alembic upgrade head"
    "$ALEMBIC" upgrade head
}

read_current_revision_output() {
    "$ALEMBIC" current 2>&1
}

# Probes the stamped revision BEFORE upgrading. If this checkout's migration files do
# not contain the revision the database was stamped with -- almost always another
# worktree sharing one compose project -- `alembic upgrade` dies with a raw traceback
# and, under a restart loop, crash-loops. Print the remedy instead.
refuse_unknown_revision() {
    probe="$1"
    probe_rc="$2"
    if [ "$probe_rc" -ne 0 ] && printf '%s\n' "$probe" | grep -q "Can't locate revision identified by"; then
        bad="$(printf '%s\n' "$probe" | sed -n "s/.*identified by '\([^']*\)'.*/\1/p" | head -n1)"
        {
            echo "DATABASE / CHECKOUT MISMATCH"
            echo "This database was stamped with revision '${bad}', which this checkout does not have."
            echo "Another worktree almost certainly ran the stack against the same compose project."
            echo "Fix (wipes the LOCAL dev DB; it re-migrates on next start):  make clean && make start"
            echo "Or start from the checkout that owns revision '${bad}'."
        } >&2
        exit 1
    fi
}

run_entrypoint "$@"
