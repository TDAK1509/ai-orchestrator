import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.agent import Agent
from models.base import Base
from models.task import Task
from models.worktree import TaskWorktree
from runtime import worktree as worktree_ops
from runtime.runtime_service import RuntimeService, RuntimeSettings

FAKE_CLAUDE = Path(__file__).parent / "fixtures" / "fake_claude.py"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def git_repo(tmp_path) -> Path:
    repo_root = tmp_path / "repo"
    await worktree_ops.run_git(["init", "-b", "main", str(repo_root)], cwd=tmp_path)
    await worktree_ops.run_git(["config", "user.email", "test@example.com"], cwd=repo_root)
    await worktree_ops.run_git(["config", "user.name", "Test"], cwd=repo_root)
    (repo_root / "README.md").write_text("seed\n")
    await worktree_ops.run_git(["add", "-A"], cwd=repo_root)
    await worktree_ops.run_git(["commit", "-m", "seed"], cwd=repo_root)
    return repo_root


@pytest_asyncio.fixture
async def task_worktree(db_session, git_repo, tmp_path) -> TaskWorktree:
    task = Task(id=uuid.uuid4(), title="Fix refresh-token rotation")
    db_session.add(task)
    path = tmp_path / "worktrees" / str(task.id)
    await worktree_ops.create_worktree(git_repo, f"agent-office/{task.id}", path, "main")
    record = TaskWorktree(
        id=uuid.uuid4(), task_id=task.id, branch=f"agent-office/{task.id}", base_branch="main", path=str(path)
    )
    db_session.add(record)
    await db_session.flush()
    return task, record


@pytest_asyncio.fixture
async def agent(db_session) -> Agent:
    record = Agent(id=uuid.uuid4(), name="Alex", role="Backend Engineer", instructions="")
    db_session.add(record)
    await db_session.flush()
    return record


@pytest.fixture
def runtime_service(db_session, tmp_path) -> RuntimeService:
    settings = RuntimeSettings(claude_binary=str(FAKE_CLAUDE), runtime_root=tmp_path / "runtime")
    return RuntimeService(db_session, settings)
