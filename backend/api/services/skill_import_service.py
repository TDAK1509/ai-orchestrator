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
# allow-comment: a total across SKILL.md plus every inlined sibling (PR 3) -- a skill directory is not guaranteed to be small, so one file's cap isn't enough. Kept well below MAX_SKILL_MD_BYTES's ceiling: this text is inlined into every session an assigned agent starts, uncapped in aggregate across an agent's other skills, so one skill should stay a small slice of the prompt budget.
MAX_SKILL_TOTAL_BYTES = 200_000
BINARY_FILE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".otf",
    ".mp3", ".mp4", ".mov", ".wav", ".so", ".dylib", ".dll", ".exe", ".bin",
}

IMPORT_LOCK = asyncio.Lock()


@dataclass
class ImportedSkillFile:
    slug: str
    name: str
    description: str | None
    instructions: str
    skipped_files: list[str] = field(default_factory=list)


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
    skill_md_size = skill_md.stat().st_size
    if skill_md_size > MAX_SKILL_MD_BYTES:
        errors.append(f"{entry.name}: SKILL.md exceeds {MAX_SKILL_MD_BYTES} bytes, skipped")
        return None
    return assemble_imported_skill_file(entry, skill_md, skill_md_size)


def assemble_imported_skill_file(entry: Path, skill_md: Path, skill_md_size: int) -> ImportedSkillFile:
    """A skipped sibling is informational, never fatal to the scan (unlike `errors` above): the migration that seeds the skills table on a fresh install aborts the whole scan on any entry in `errors`, and an oversized reference file must not take the rest of the catalog down with it."""
    front_matter, instructions = split_front_matter(skill_md.read_text())
    skipped: list[str] = []
    instructions = inline_sibling_files(entry, skill_md, skill_md_size, instructions, skipped)
    return build_imported_skill_file_record(entry, front_matter, instructions, skipped)


def build_imported_skill_file_record(entry: Path, front_matter: dict[str, str], instructions: str, skipped: list[str]) -> ImportedSkillFile:
    slug = entry.name
    return ImportedSkillFile(
        slug=slug,
        name=front_matter.get("name") or slug,
        description=front_matter.get("description"),
        instructions=instructions,
        skipped_files=skipped,
    )


def inline_sibling_files(entry: Path, skill_md: Path, skill_md_size: int, instructions: str, skipped: list[str]) -> str:
    """A skill authored for Claude Code can tell an agent to read a file beside SKILL.md (e.g. `references/examples.md`) that no agent can reach -- inline it instead of leaving a dangling path (PR 3)."""
    budget = MAX_SKILL_TOTAL_BYTES - skill_md_size
    resolved_entry = entry.resolve()
    siblings = sorted(path for path in entry.rglob("*") if path.is_file() and path != skill_md)
    blocks = [instructions]
    for sibling in siblings:
        block, budget = read_sibling_block(sibling, entry, resolved_entry, budget, skipped)
        if block is not None:
            blocks.append(block)
    return "\n\n".join(blocks)


def read_sibling_block(sibling: Path, entry: Path, resolved_entry: Path, budget: int, skipped: list[str]) -> tuple[str | None, int]:
    relative = sibling.relative_to(entry)
    if not sibling.resolve().is_relative_to(resolved_entry):
        skipped.append(f"{entry.name}: {relative} skipped, a symlink leading outside the skill directory")
        return None, budget
    if sibling.suffix.lower() in BINARY_FILE_EXTENSIONS:
        return None, budget
    size = sibling.stat().st_size
    if size > budget:
        skipped.append(f"{entry.name}: {relative} skipped, exceeds the {MAX_SKILL_TOTAL_BYTES}-byte total cap")
        return None, budget
    return read_sibling_text_block(sibling, relative, entry, size, budget, skipped)


def read_sibling_text_block(sibling: Path, relative: Path, entry: Path, size: int, budget: int, skipped: list[str]) -> tuple[str | None, int]:
    try:
        text = sibling.read_text()
    except (OSError, UnicodeDecodeError) as exc:
        skipped.append(f"{entry.name}: {relative}: {exc}")
        return None, budget
    return f"## {relative}\n\n{text}", budget - size


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
    summary.skipped.extend(skill_file.skipped_files)
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
