from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.codex.codex_headless import find_repo_root, resolve_codex_home
from backend.codex.history import list_sessions, read_session_messages

router = APIRouter(prefix="/codex")


class SessionSummaryResponse(BaseModel):
    id: str
    title: str | None
    started_at: str | None
    cwd: str | None
    originator: str | None


class ConversationMessageResponse(BaseModel):
    role: str
    text: str
    timestamp: str | None = None
    phase: str | None = None


class SessionDetailResponse(BaseModel):
    id: str
    messages: list[ConversationMessageResponse]


@router.get("/sessions", response_model=list[SessionSummaryResponse])
async def codex_sessions(
    limit: int = Query(default=50, ge=1, le=500),
    all_repos: bool = Query(default=False),
) -> list[SessionSummaryResponse]:
    repo_root = find_repo_root(Path.cwd())
    codex_home = resolve_codex_home(repo_root)

    sessions = list_sessions(
        codex_home,
        repo_root=repo_root,
        include_all_repos=all_repos,
        limit=limit,
    )
    return [
        SessionSummaryResponse(
            id=s.session_id,
            title=s.title,
            started_at=s.started_at.isoformat() if s.started_at else None,
            cwd=s.cwd,
            originator=s.originator,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def codex_session_detail(
    session_id: str,
    include_roles: str = Query(default="user,assistant,developer"),
) -> SessionDetailResponse:
    repo_root = find_repo_root(Path.cwd())
    codex_home = resolve_codex_home(repo_root)

    roles = {r.strip() for r in include_roles.split(",") if r.strip()}
    msgs = read_session_messages(codex_home, session_id, include_roles=roles)
    if not msgs:
        raise HTTPException(status_code=404, detail="Session not found (or no readable messages)")

    return SessionDetailResponse(
        id=session_id,
        messages=[
            ConversationMessageResponse(
                role=m.role,
                text=m.text,
                timestamp=m.timestamp.isoformat() if m.timestamp else None,
                phase=m.phase,
            )
            for m in msgs
        ],
    )

