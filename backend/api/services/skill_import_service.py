import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from db import commit
from models.skill import Skill, SkillSource
from services.skill_service import delete_skill_assignments, list_assigned_agents

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
    removed: list[Skill] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    unassigned: list[dict] = field(default_factory=list)


def claude_code_skills_dir() -> Path:
    override = os.environ.get("AGENT_OFFICE_CLAUDE_SKILLS_DIR")
    return Path(override) if override else DEFAULT_CLAUDE_SKILLS_DIR


async def import_claude_code_skills(db, directory: Path, slugs: list[str] | None = None) -> ImportSummary:
    """One-way sync (README 15): reads Claude Code's own skill directory and never writes back to it. Serialized process-wide, so two presses racing on the same new slug can't both decide to insert it."""
    async with IMPORT_LOCK:
        summary = ImportSummary()
        skill_files, summary.errors = await asyncio.to_thread(scan_claude_code_skills, directory)
        await apply_selected_skills(db, index_skill_files_by_slug(skill_files), slugs, summary)
        await commit(db)
        return summary


async def apply_selected_skills(db, skill_files_by_slug: dict[str, ImportedSkillFile], slugs: list[str] | None, summary: ImportSummary) -> None:
    """`slugs=None` means every skill on disk, the original behaviour with no removals; an explicit list is PR 2's sync-by-selection, which also removes an IMPORTED skill that is not on the list."""
    existing = await load_skills_by_slug(db)
    wanted_slugs = set(slugs) if slugs is not None else set(skill_files_by_slug)
    apply_wanted_skills(db, wanted_slugs, skill_files_by_slug, existing, summary)
    if slugs is not None:
        await remove_unwanted_imported_skills(db, wanted_slugs, existing, summary)


async def list_available_skills(db, directory: Path) -> list[dict]:
    """PR 1: names only, no instructions or file contents -- reads just SKILL.md's front matter, never a sibling file, so opening the picker never pays PR 3's full inlining cost. A union of what's on disk and what's already imported, so a since-vanished directory still shows up (`on_disk: false`) instead of becoming permanently unremovable through this screen."""
    on_disk = await asyncio.to_thread(scan_available_skill_names, directory)
    imported = await load_imported_skills_by_slug(db)
    return [build_available_entry(slug, on_disk, imported) for slug in sorted(set(on_disk) | set(imported))]


def scan_available_skill_names(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        return {}
    names: dict[str, str] = {}
    for entry in sorted(directory.iterdir()):
        read_available_skill_name(entry, names)
    return names


def read_available_skill_name(entry: Path, names: dict[str, str]) -> None:
    skill_md = entry / "SKILL.md"
    if not entry.is_dir() or not skill_md.is_file():
        return
    try:
        front_matter, _ = split_front_matter(read_front_matter_prefix(skill_md))
    except OSError:
        return
    names[entry.name] = front_matter.get("name") or entry.name


def read_front_matter_prefix(skill_md: Path, limit: int = 8_192) -> str:
    """A front matter block is a handful of lines -- reading a small prefix instead of the whole file is what keeps this listing cheap."""
    with skill_md.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read(limit)


async def load_imported_skills_by_slug(db) -> dict[str, Skill]:
    query = select(Skill).where(Skill.source == SkillSource.IMPORTED)
    return {skill.slug: skill for skill in (await db.execute(query)).scalars()}


def build_available_entry(slug: str, on_disk: dict[str, str], imported: dict[str, Skill]) -> dict:
    name = on_disk[slug] if slug in on_disk else imported[slug].name
    return {"slug": slug, "name": name, "in_catalog": slug in imported, "on_disk": slug in on_disk}


def index_skill_files_by_slug(skill_files: list[ImportedSkillFile | None]) -> dict[str, ImportedSkillFile]:
    return {skill_file.slug: skill_file for skill_file in skill_files if skill_file is not None}


def apply_wanted_skills(
    db, wanted_slugs: set[str], skill_files_by_slug: dict[str, ImportedSkillFile], existing: dict[str, Skill], summary: ImportSummary
) -> None:
    for slug in wanted_slugs:
        skill_file = skill_files_by_slug.get(slug)
        if skill_file is None:
            summary.errors.append(f"{slug}: ticked but not found on disk, skipped")
            continue
        apply_imported_skill(db, existing.get(slug), skill_file, summary)


async def remove_unwanted_imported_skills(db, wanted_slugs: set[str], existing: dict[str, Skill], summary: ImportSummary) -> None:
    """Only ever removes an IMPORTED skill (PR 2): a CUSTOM skill that happens to share a slug with something absent from the list is never touched."""
    for slug, skill in existing.items():
        if slug in wanted_slugs or skill.source != SkillSource.IMPORTED:
            continue
        await remove_imported_skill(db, skill, summary)


async def remove_imported_skill(db, skill: Skill, summary: ImportSummary) -> None:
    """The assigned-agent names are read before the assignment rows are deleted -- after that, the information needed to name the cost is gone."""
    agents = await list_assigned_agents(db, skill.id)
    summary.unassigned.append({"slug": skill.slug, "agents": [agent.name for agent in agents]})
    summary.removed.append(skill)
    await delete_skill_assignments(db, skill.id)
    await db.delete(skill)


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
