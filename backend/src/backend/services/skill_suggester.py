from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

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
    def __init__(
        self,
        *,
        store: ConversationStore,
        openai_api_key: str,
        model: str,
    ) -> None:
        self._store = store
        self._model = model

        self._client = OpenAI(api_key=openai_api_key)

    def ingest_and_suggest(
        self,
        *,
        session_id: str,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._store.save_events(session_id, events)
        history = self._store.get_history(session_id)

        analysis = self._analyze_history(history=history)

        if not analysis.get("should_suggest"):
            return {"status": "ok"}

        suggestion_type = str(analysis.get("suggestion_type", "none")).lower()
        message = str(
            analysis.get("message", "Consider adding this guidance to a project skill.")
        )

        if suggestion_type == "existing":
            existing_skill_name = str(analysis.get("existing_skill_name", "")).strip().lower()
            for skill in EXISTING_SKILLS:
                if skill.name.lower() == existing_skill_name:
                    return {
                        "status": "suggested_existing_skill",
                        "message": message,
                        "skill": {
                            "name": skill.name,
                            "path": skill.path,
                            "description": skill.description,
                        },
                    }

            # If the model asks for existing but we cannot map it, fall back to no-op.
            return {"status": "ok"}

        if suggestion_type != "new":
            return {"status": "ok"}

        skill_name = self._slugify(str(analysis.get("new_skill_name", "session-insights-skill")))
        if not skill_name:
            skill_name = "session-insights-skill"
        new_skill_description = str(
            analysis.get(
                "new_skill_description",
                "Skill synthesized from repeated conversation corrections.",
            )
        )

        return {
            "status": "suggested_new_skill",
            "message": message,
            "skill": {
                "name": skill_name,
                "path": f".codex/skills/{skill_name}/SKILL.md",
                "description": new_skill_description,
            },
        }

    def _analyze_history(self, *, history: list[dict[str, Any]]) -> dict[str, Any]:
        if not history:
            return {"should_suggest": False}

        history_lines: list[str] = []
        for item in history[-80:]:
            speaker = str(item.get("speaker", "unknown"))
            message = str(item.get("message", "")).strip()
            if message:
                history_lines.append(f"{speaker}: {message}")

        if not history_lines:
            return {"should_suggest": False}

        existing_skills_block = "\n".join(
            f"- {skill.name}: {skill.description} ({skill.path})" for skill in EXISTING_SKILLS
        )
        prompt = (
            "You analyze coding conversation history and decide if a skill suggestion should be emitted.\n"
            "Return strict JSON with keys:\n"
            "should_suggest (boolean), suggestion_type ('none'|'existing'|'new'), "
            "existing_skill_name (string), new_skill_name (string), "
            "new_skill_description (string), message (string).\n"
            "Rules:\n"
            "- should_suggest=true only if the user gives a durable correction/instruction to remember.\n"
            "- suggestion_type='existing' only if one of the existing skills clearly matches.\n"
            "- suggestion_type='new' only if a new reusable skill is justified.\n"
            "- If uncertain, set should_suggest=false and suggestion_type='none'.\n\n"
            f"Existing skills:\n{existing_skills_block}\n\n"
            "Conversation history:\n"
            f"{chr(10).join(history_lines)}"
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict JSON classifier for skill suggestions.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {"should_suggest": False}

        return {"should_suggest": False}

    @staticmethod
    def _slugify(name: str) -> str:
        normalized = name.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
        normalized = normalized.strip("-")
        return normalized[:50]
