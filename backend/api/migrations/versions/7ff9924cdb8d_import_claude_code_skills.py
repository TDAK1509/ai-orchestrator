"""import claude code skills

Revision ID: 7ff9924cdb8d
Revises: 255dab01ce1e
Create Date: 2026-09-05 07:00:00.000000

This migration retires the repository-mirrored GLOBAL skill source in favor
of one imported straight from Claude Code's own skill directory
(~/.claude/skills, or AGENT_OFFICE_CLAUDE_SKILLS_DIR). It does not convert
the old rows -- it deletes every GLOBAL skill and re-imports from disk in
the same transaction, so the catalog is never empty between deploys.

A GLOBAL skill an agent still holds is captured by (agent_id, slug) before
the delete, and re-linked by slug once the newly imported rows exist -- the
DELETE from agent_skill_assignments and the INSERT into it further down are
the same repair, not two unrelated migrations that happened to land here.
A slug with no match on disk (or none an agent held) is simply not relinked.
"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from services.skill_import_service import (
    claude_code_skills_dir,
    scan_claude_code_skills,
)

revision: str = '7ff9924cdb8d'
down_revision: str | None = '255dab01ce1e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    reassignments = capture_global_assignments(bind)
    delete_global_assignments(bind)
    delete_global_skills(bind)
    imported_ids_by_slug = insert_imported_skills(bind)
    relink_assignments(bind, reassignments, imported_ids_by_slug)


def capture_global_assignments(bind) -> list[tuple[str, str]]:
    rows = bind.execute(
        sa.text(
            "SELECT a.agent_id AS agent_id, s.slug AS slug FROM agent_skill_assignments a "
            "JOIN skills s ON s.id = a.skill_id WHERE s.source = 'GLOBAL'"
        )
    ).all()
    return [(row.agent_id, row.slug) for row in rows]


def delete_global_assignments(bind) -> None:
    bind.execute(
        sa.text("DELETE FROM agent_skill_assignments WHERE skill_id IN (SELECT id FROM skills WHERE source = 'GLOBAL')")
    )


def delete_global_skills(bind) -> None:
    bind.execute(sa.text("DELETE FROM skills WHERE source = 'GLOBAL'"))


def insert_imported_skills(bind) -> dict[str, str]:
    """Skips a slug that a CUSTOM row already owns -- same collision rule the importer applies on every later press of the button."""
    skill_files, _errors = scan_claude_code_skills(claude_code_skills_dir())
    existing_slugs = {row[0] for row in bind.execute(sa.text("SELECT slug FROM skills")).all()}
    ids_by_slug: dict[str, str] = {}
    for skill_file in skill_files:
        if skill_file.slug in existing_slugs:
            continue
        skill_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO skills (id, slug, name, description, source, instructions, created_at, updated_at) "
                "VALUES (:id, :slug, :name, :description, 'IMPORTED', :instructions, now(), now())"
            ),
            {
                "id": skill_id,
                "slug": skill_file.slug,
                "name": skill_file.name,
                "description": skill_file.description,
                "instructions": skill_file.instructions,
            },
        )
        ids_by_slug[skill_file.slug] = skill_id
    return ids_by_slug


def relink_assignments(bind, reassignments: list[tuple[str, str]], ids_by_slug: dict[str, str]) -> None:
    for agent_id, slug in reassignments:
        skill_id = ids_by_slug.get(slug)
        if skill_id is None:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO agent_skill_assignments (id, agent_id, skill_id, created_at) "
                "VALUES (:id, :agent_id, :skill_id, now()) ON CONFLICT DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "agent_id": agent_id, "skill_id": skill_id},
        )


def downgrade() -> None:
    raise RuntimeError(
        "no downgrade: the GLOBAL rows this migration deletes cannot be reconstructed, and the "
        "repository-mirrored skills/ directory they came from is gone from this branch"
    )
