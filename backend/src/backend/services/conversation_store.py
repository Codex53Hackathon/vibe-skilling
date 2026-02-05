from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pymongo import ASCENDING, MongoClient

from backend.core.config import Settings


class ConversationStore(Protocol):
    def save_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        ...

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        ...


class MongoConversationStore:
    def __init__(self, settings: Settings) -> None:
        self._asc = ASCENDING
        self._client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
        self._collection = self._client[settings.mongo_database][settings.mongo_collection]
        self._collection.create_index(
            [("session_id", self._asc), ("created_at", self._asc)]
        )
        self._client.admin.command("ping")

    def save_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        docs: list[dict[str, Any]] = []
        now = datetime.now(UTC).isoformat()
        for event in events:
            docs.append(
                {
                    "session_id": session_id,
                    "speaker": event.get("speaker"),
                    "message": event.get("message"),
                    "timestamp": event.get("timestamp"),
                    "source": event.get("source"),
                    "created_at": now,
                }
            )

        if docs:
            self._collection.insert_many(docs)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        cursor = self._collection.find(
            {"session_id": session_id},
            {
                "_id": 0,
                "session_id": 1,
                "speaker": 1,
                "message": 1,
                "timestamp": 1,
                "source": 1,
                "created_at": 1,
            },
        ).sort("created_at", self._asc)
        return list(cursor)


def create_conversation_store(settings: Settings) -> ConversationStore:
    return MongoConversationStore(settings)
