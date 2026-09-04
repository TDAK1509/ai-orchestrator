from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from runtime.runtime_service import RuntimeService
from services.task_service import TaskRuntimePolicy


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as db:
        yield db


def get_runtime_service(request: Request) -> RuntimeService:
    return request.app.state.runtime_service


def get_repo_root(request: Request) -> Path:
    return request.app.state.repo_root


def get_policy(request: Request) -> TaskRuntimePolicy:
    return request.app.state.policy
