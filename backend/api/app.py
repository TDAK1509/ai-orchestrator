import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth import get_allowed_origins, require_api_token
from db import build_engine, build_session_factory
from routers import (
    agents,
    attention,
    decisions,
    events,
    filesystem,
    mcp,
    meetings,
    memory,
    repositories,
    rooms,
    skills,
    tasks,
    teams,
)
from runtime.backend_lock import BackendLock
from runtime.runtime_service import RuntimeService, RuntimeSettings
from services.embedding_service import prewarm_embedding_model
from services.memory_sweep_service import start_memory_sweep, stop_memory_sweep
from services.run_driver import shutdown_background_runs
from services.startup_service import reconcile_on_startup
from services.task_service import TaskRuntimePolicy
from services.watchdog_service import start_watchdog, stop_watchdog


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = build_engine()
    initialize_app_state(app, engine)
    lock = BackendLock(app.state.runtime_service.settings.runtime_root / "backend.lock")
    lock.acquire()
    try:
        await reconcile_and_start_watchdog(app)
        yield
        await drain_and_stop(app)
    finally:
        lock.release()
    await engine.dispose()


def initialize_app_state(app: FastAPI, engine) -> None:
    app.state.session_factory = build_session_factory(engine)
    app.state.runtime_service = RuntimeService(app.state.session_factory, build_runtime_settings_from_env())
    app.state.repo_root = Path(os.environ.get("AGENT_OFFICE_REPO_ROOT", "."))
    app.state.policy = build_policy_from_env()


async def reconcile_and_start_watchdog(app: FastAPI) -> None:
    await prewarm_embedding_model()
    async with app.state.session_factory() as db:
        await reconcile_on_startup(db, app.state.runtime_service, app.state.repo_root, app.state.policy)
    app.state.watchdog_task = start_watchdog(app.state.runtime_service)
    app.state.memory_sweep_task = start_memory_sweep(app.state.session_factory)


async def drain_and_stop(app: FastAPI) -> None:
    await stop_watchdog(app.state.watchdog_task)
    await stop_memory_sweep(app.state.memory_sweep_task)
    await shutdown_background_runs(app.state.runtime_service)


def build_policy_from_env() -> TaskRuntimePolicy:
    return TaskRuntimePolicy(max_concurrent_agents=int(os.environ.get("MAX_CONCURRENT_AGENTS", "3")))


def build_runtime_settings_from_env() -> RuntimeSettings:
    settings = RuntimeSettings()
    if claude_binary := os.environ.get("AGENT_OFFICE_CLAUDE_BINARY"):
        settings.claude_binary = claude_binary
    if runtime_root := os.environ.get("AGENT_OFFICE_RUNTIME_ROOT"):
        settings.runtime_root = Path(runtime_root)
    if effort := os.environ.get("AGENT_OFFICE_DEFAULT_EFFORT"):
        settings.effort = effort
    return settings


app = FastAPI(title="Agent Office", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


for router_module in (agents, tasks, decisions, skills, mcp, memory, rooms, meetings, attention, teams, filesystem, repositories):
    app.include_router(router_module.router, dependencies=[Depends(require_api_token)])

# allow-comment: events.router's /ws route enforces its own origin+token check (see auth.authorize_websocket) instead of Depends(require_api_token) below, since a failed WebSocket handshake can't be turned into an HTTP 401.
app.include_router(events.router)
