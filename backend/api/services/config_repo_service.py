import hashlib
from pathlib import Path

from runtime import worktree as worktree_ops

CONFIG_BRANCH = "agent-office/config"


async def ensure_config_worktree(repo_root: Path, base_branch: str = "main") -> Path:
    """One long-lived worktree for the Skill Catalog (README 19.3), a sibling of repo_root and separate from any task worktree."""
    path = repo_root.parent / ".agent-office" / f"config-{repo_fingerprint(repo_root)}"
    await worktree_ops.create_worktree(repo_root, CONFIG_BRANCH, path, base_branch)
    return path


def repo_fingerprint(repo_root: Path) -> str:
    """Two different repos with the same parent directory must never resolve to the same worktree path."""
    return hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:12]
