from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

class ConversationStore(Protocol):
    def save_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        ...

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        ...


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, Any]]] = {}

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

        self._sessions.setdefault(session_id, []).extend(docs)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        return list(self._sessions.get(session_id, []))


def create_conversation_store() -> ConversationStore:
    return InMemoryConversationStore()
