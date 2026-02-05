from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.config import get_settings
from backend.services.conversation_store import create_conversation_store
from backend.services.skill_suggester import SkillSuggestionService

router = APIRouter(prefix="/conversation")


class ConversationEvent(BaseModel):
    speaker: str = Field(min_length=1)
    message: str = Field(min_length=1)
    timestamp: datetime | None = None
    source: str | None = None


class IngestRequest(BaseModel):
    session_id: str = Field(min_length=1)
    events: list[ConversationEvent] = Field(min_length=1)


class SkillSuggestion(BaseModel):
    name: str
    path: str
    description: str


class IngestResponse(BaseModel):
    status: Literal["ok", "suggested_existing_skill", "suggested_new_skill"]
    message: str | None = None
    skill: SkillSuggestion | None = None


@lru_cache(maxsize=1)
def get_skill_suggestion_service() -> SkillSuggestionService:
    settings = get_settings()
    if not settings.mongo_uri:
        raise RuntimeError("MONGODB_URI is not configured")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    store = create_conversation_store(settings)
    return SkillSuggestionService(
        store=store,
        openai_api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


@router.post("/ingest", response_model=IngestResponse)
def ingest_conversation(payload: IngestRequest) -> IngestResponse:
    try:
        service = get_skill_suggestion_service()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response_payload = service.ingest_and_suggest(
        session_id=payload.session_id,
        events=[event.model_dump(mode="json") for event in payload.events],
    )
    return IngestResponse.model_validate(response_payload)
