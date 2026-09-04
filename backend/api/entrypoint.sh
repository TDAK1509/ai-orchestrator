#!/usr/bin/env sh
# Migrations run here, not in the Makefile, so they happen whenever the backend
# starts -- including a direct ./backend/api/entrypoint.sh, not only `make start`.
set -eu
cd "$(dirname "$0")"

if [ "${AGENT_OFFICE_AUTO_MIGRATE:-1}" = "1" ]; then
    # Probe the stamped revision BEFORE upgrading. If this checkout's migration files
    # do not contain the revision the database was stamped with -- almost always another
    # worktree sharing one compose project -- `alembic upgrade` dies with a raw traceback
    # and, under a restart loop, crash-loops. Print the remedy instead.
    set +e
    probe="$("$ALEMBIC" current 2>&1)"; probe_rc=$?
    set -e
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
    echo "[entrypoint] alembic upgrade head"
    "$ALEMBIC" upgrade head
else
    echo "[entrypoint] AGENT_OFFICE_AUTO_MIGRATE=0; skipping migrations."
fi

exec "$UVICORN" app:app --port 8000 "$@"
