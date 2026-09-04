import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import build_engine, build_session_factory
from routers import (
    agents,
    attention,
    decisions,
    events,
    mcp,
    meetings,
    memory,
    rooms,
    skills,
    tasks,
)
from runtime.runtime_service import RuntimeService, RuntimeSettings
from services.startup_service import reconcile_on_startup
from services.task_service import TaskRuntimePolicy


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = build_engine()
    app.state.session_factory = build_session_factory(engine)
    app.state.runtime_service = RuntimeService(app.state.session_factory, build_runtime_settings_from_env())
    app.state.repo_root = Path(os.environ.get("AGENT_OFFICE_REPO_ROOT", "."))
    app.state.policy = build_policy_from_env()
    async with app.state.session_factory() as db:
        await reconcile_on_startup(db, app.state.runtime_service)
    yield
    await engine.dispose()


def build_policy_from_env() -> TaskRuntimePolicy:
    return TaskRuntimePolicy(max_concurrent_agents=int(os.environ.get("MAX_CONCURRENT_AGENTS", "3")))


def build_runtime_settings_from_env() -> RuntimeSettings:
    settings = RuntimeSettings()
    if claude_binary := os.environ.get("AGENT_OFFICE_CLAUDE_BINARY"):
        settings.claude_binary = claude_binary
    if runtime_root := os.environ.get("AGENT_OFFICE_RUNTIME_ROOT"):
        settings.runtime_root = Path(runtime_root)
    return settings


app = FastAPI(title="Agent Office", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("AGENT_OFFICE_CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


for router_module in (agents, tasks, decisions, skills, mcp, memory, rooms, meetings, attention, events):
    app.include_router(router_module.router)
