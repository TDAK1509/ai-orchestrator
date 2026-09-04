import os

from fastapi import Header, HTTPException, WebSocket


async def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """No-op when unset (the default local-dev case): set AGENT_OFFICE_API_TOKEN to require a bearer token on every HTTP request, e.g. for a VPS deployment reachable beyond localhost."""
    token = get_required_token()
    if token is not None and authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="missing or invalid bearer token")


async def authorize_websocket(websocket: WebSocket) -> bool:
    """No HTTP response is possible once a WebSocket handshake starts, so the caller must close the socket itself on a False return rather than relying on an exception."""
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in get_allowed_origins():
        return False
    token = get_required_token()
    return token is None or websocket.headers.get("authorization") == f"Bearer {token}"


def get_allowed_origins() -> list[str]:
    return os.environ.get("AGENT_OFFICE_CORS_ORIGINS", "http://localhost:5173").split(",")


def get_required_token() -> str | None:
    return os.environ.get("AGENT_OFFICE_API_TOKEN")
