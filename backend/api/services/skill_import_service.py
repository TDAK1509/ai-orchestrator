import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from db import commit
from models.skill import Skill, SkillSource

DEFAULT_CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"
MAX_SKILL_MD_BYTES = 1_000_000

IMPORT_LOCK = asyncio.Lock()


@dataclass
class ImportedSkillFile:
    slug: str
    name: str
    description: str | None
    instructions: str


@dataclass
class ImportSummary:
    created: list[Skill] = field(default_factory=list)
    updated: list[Skill] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def claude_code_skills_dir() -> Path:
    override = os.environ.get("AGENT_OFFICE_CLAUDE_SKILLS_DIR")
    return Path(override) if override else DEFAULT_CLAUDE_SKILLS_DIR


async def import_claude_code_skills(db, directory: Path) -> ImportSummary:
    """One-way sync (README 15): reads Claude Code's own skill directory and never writes back to it. Serialized process-wide, so two presses racing on the same new slug can't both decide to insert it."""
    async with IMPORT_LOCK:
        summary = ImportSummary()
        skill_files, summary.errors = await asyncio.to_thread(scan_claude_code_skills, directory)
        existing = await load_skills_by_slug(db)
        for skill_file in skill_files:
            if skill_file is not None:
                apply_imported_skill(db, existing.get(skill_file.slug), skill_file, summary)
        await commit(db)
        return summary


def scan_claude_code_skills(directory: Path) -> tuple[list[ImportedSkillFile], list[str]]:
    if not directory.is_dir():
        return [], []
    skill_files: list[ImportedSkillFile] = []
    errors: list[str] = []
    for entry in sorted(directory.iterdir()):
        read_claude_code_skill(entry, skill_files, errors)
    return skill_files, errors


def read_claude_code_skill(entry: Path, skill_files: list[ImportedSkillFile], errors: list[str]) -> None:
    """Symlinks are followed here, unlike the old repo mirror: ~/.claude/skills is almost entirely symlinks into a Claude Code checkout the user already trusts, not a repo directory a stray link could escape. `is_file()` still guards against a FIFO or device node that a `read_text()` could hang or blow memory on, and the size cap below catches an oversized regular file."""
    skill_md = entry / "SKILL.md"
    if not entry.is_dir() or not skill_md.is_file():
        return
    try:
        skill_files.append(build_imported_skill_file(entry, skill_md, errors))
    except OSError as exc:
        errors.append(f"{entry.name}: {exc}")


def build_imported_skill_file(entry: Path, skill_md: Path, errors: list[str]) -> ImportedSkillFile | None:
    if skill_md.stat().st_size > MAX_SKILL_MD_BYTES:
        errors.append(f"{entry.name}: SKILL.md exceeds {MAX_SKILL_MD_BYTES} bytes, skipped")
        return None
    front_matter, instructions = split_front_matter(skill_md.read_text())
    slug = entry.name
    return ImportedSkillFile(
        slug=slug,
        name=front_matter.get("name") or slug,
        description=front_matter.get("description"),
        instructions=instructions,
    )


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """A SKILL.md authored for Claude Code opens with a YAML front matter block naming the skill for Claude Code's own dispatcher. Strip it: the result is inlined verbatim into an assigned agent's first message (README 32.3), and that block addresses Claude Code's dispatcher, not the agent."""
    if not text.startswith("---\n"):
        return {}, text
    block, separator, body = text[4:].partition("\n---\n")
    if not separator:
        return {}, text
    return parse_front_matter_fields(block), body.lstrip("\n")


def parse_front_matter_fields(block: str) -> dict[str, str]:
    """Top-level `key: value` lines only -- enough for name and description, and it keeps a YAML parser out of the dependency list. An indented or multi-line value is ignored, not half-read."""
    fields = {}
    for line in block.splitlines():
        key, separator, value = line.partition(":")
        if separator and not line.startswith((" ", "\t")):
            fields[key.strip()] = value.strip()
    return fields


async def load_skills_by_slug(db) -> dict[str, Skill]:
    return {skill.slug: skill for skill in (await db.execute(select(Skill))).scalars()}


def apply_imported_skill(db, existing: Skill | None, skill_file: ImportedSkillFile, summary: ImportSummary) -> None:
    if existing is None:
        skill = build_imported_skill(skill_file)
        db.add(skill)
        summary.created.append(skill)
        return
    if existing.source != SkillSource.IMPORTED:
        summary.skipped.append(skill_file.slug)
        return
    update_imported_skill(existing, skill_file)
    summary.updated.append(existing)


def build_imported_skill(skill_file: ImportedSkillFile) -> Skill:
    return Skill(
        id=uuid.uuid4(),
        slug=skill_file.slug,
        name=skill_file.name,
        description=skill_file.description,
        source=SkillSource.IMPORTED,
        instructions=skill_file.instructions,
    )


def update_imported_skill(skill: Skill, skill_file: ImportedSkillFile) -> None:
    skill.name = skill_file.name
    skill.description = skill_file.description
    skill.instructions = skill_file.instructions
