import pytest

from runtime import worktree


async def test_create_worktree_checks_out_a_new_branch(git_repo, tmp_path):
    path = tmp_path / "wt"
    await worktree.create_worktree(git_repo, "agent-office/TASK-1", path, "main")
    assert path.exists()
    head = await worktree.read_head_commit(path)
    assert head


async def test_create_worktree_is_idempotent_for_the_same_branch(git_repo, tmp_path):
    path = tmp_path / "wt"
    await worktree.create_worktree(git_repo, "agent-office/TASK-1b", path, "main")
    await worktree.create_worktree(git_repo, "agent-office/TASK-1b", path, "main")
    assert path.exists()


async def test_create_worktree_rejects_a_path_reused_for_a_different_branch(git_repo, tmp_path):
    path = tmp_path / "wt"
    await worktree.create_worktree(git_repo, "agent-office/TASK-1c", path, "main")
    with pytest.raises(worktree.WorktreeMismatchError):
        await worktree.create_worktree(git_repo, "agent-office/TASK-1d", path, "main")


async def test_commit_worktree_returns_none_when_nothing_changed(git_repo, tmp_path):
    path = tmp_path / "wt"
    await worktree.create_worktree(git_repo, "agent-office/TASK-2", path, "main")
    assert await worktree.commit_worktree(path, "no-op") is None


async def test_commit_worktree_returns_new_sha_when_files_changed(git_repo, tmp_path):
    path = tmp_path / "wt"
    await worktree.create_worktree(git_repo, "agent-office/TASK-3", path, "main")
    before = await worktree.read_head_commit(path)
    (path / "output.txt").write_text("done\n")
    after = await worktree.commit_worktree(path, "do the work")
    assert after is not None
    assert after != before
