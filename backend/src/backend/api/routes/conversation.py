from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

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
    store = create_conversation_store()
    return SkillSuggestionService(store=store)


@router.post("/ingest", response_model=IngestResponse)
def ingest_conversation(payload: IngestRequest) -> IngestResponse:
    service = get_skill_suggestion_service()
    response_payload = service.ingest_and_suggest(
        session_id=payload.session_id,
        events=[event.model_dump(mode="json") for event in payload.events],
    )
    return IngestResponse.model_validate(response_payload)
