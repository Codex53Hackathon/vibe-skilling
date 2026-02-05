from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from backend.services.conversation_store import ConversationStore


@dataclass(frozen=True)
class ExistingSkill:
    name: str
    path: str
    description: str
    keywords: tuple[str, ...]


EXISTING_SKILLS: tuple[ExistingSkill, ...] = (
    ExistingSkill(
        name="db-access",
        path=".codex/skills/db-access/SKILL.md",
        description="Secure database access and query patterns.",
        keywords=("sql", "query", "database", "postgres", "mysql", "parameterized"),
    ),
    ExistingSkill(
        name="report-writer",
        path=".codex/skills/report-writer/SKILL.md",
        description="Formatting and generation of structured reports.",
        keywords=("report", "summary", "findings", "write-up"),
    ),
)


class SkillSuggestionService:
    def __init__(self, store: ConversationStore) -> None:
        self._store = store

    def ingest_and_suggest(
        self,
        *,
        session_id: str,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._store.save_events(session_id, events)
        history = self._store.get_history(session_id)

        # Demo behavior: trigger on ~1/3 of requests.
        if random.randint(1, 3) != 1:
            return {"status": "ok"}

        history_text = " ".join(
            item.get("message", "")
            for item in history
            if isinstance(item.get("message"), str)
        ).lower()

        for skill in EXISTING_SKILLS:
            if any(keyword in history_text for keyword in skill.keywords):
                return {
                    "status": "suggested_existing_skill",
                    "message": f"Consider updating the existing skill '{skill.name}'.",
                    "skill": {
                        "name": skill.name,
                        "path": skill.path,
                        "description": skill.description,
                    },
                }

        return {
            "status": "suggested_new_skill",
            "message": "Consider creating a new skill from this repeated correction.",
            "skill": {
                "name": "style-guard",
                "path": ".codex/skills/style-guard/SKILL.md",
                "description": "Style guardrails learned from conversation corrections.",
            },
        }
