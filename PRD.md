# Vibe Skilling - Live Demo PRD

## 1. Demo Goal

Show a live terminal flow where:
1. Conversation prompts and responses are sent to backend.
2. Backend stores the full conversation in temporary in-memory storage.
3. Backend responds with either:
- `ok` (no action)
- suggestion to update an existing skill
- suggestion to create a new skill

The terminal client then shows a notification when a suggestion is returned.

## 2. Scope

In scope:
- Conversation ingestion endpoint in FastAPI.
- In-memory persistence for conversation history (temporary demo mode).
- LLM analysis step (demo implementation can be mocked/heuristic).
- Hardcoded existing skills list (no external skill search API).
- Simple response contract for terminal notifications.

Out of scope:
- Automatic PR creation.
- Auto-editing skills in this phase.
- Skills registry/API integration.

## 3. API Contract

Endpoint:
- `POST /conversation/ingest`

Request:
```json
{
  "session_id": "string",
  "events": [
    {
      "speaker": "user|assistant|system",
      "message": "string",
      "timestamp": "optional ISO datetime",
      "source": "optional string"
    }
  ]
}
```

Response (option A):
```json
{
  "status": "ok"
}
```

Response (option B):
```json
{
  "status": "suggested_existing_skill",
  "message": "string",
  "skill": {
    "name": "string",
    "path": "string",
    "description": "string"
  }
}
```

Response (option C):
```json
{
  "status": "suggested_new_skill",
  "message": "string",
  "skill": {
    "name": "string",
    "path": "string",
    "description": "string"
  }
}
```

## 4. Demo Behavior (Intentionally Simple)

- Every ingest request is persisted to in-memory session history.
- Backend analyzes the conversation history for the session.
- For live demo pacing, backend randomly returns a suggestion on roughly 1 out of 3 requests.
- If suggestion is triggered:
- If topic matches a hardcoded existing skill, return `suggested_existing_skill`.
- Otherwise return `suggested_new_skill`.

## 5. Hardcoded Existing Skills (MVP)

Initial hardcoded skill map:
- `db-access` -> `.codex/skills/db-access/SKILL.md`
- `report-writer` -> `.codex/skills/report-writer/SKILL.md`

Matching approach:
- Keyword/topic match from conversation text (for example: `sql`, `query`, `database` -> `db-access`).

## 6. Key Use Case for Demo Story

Scenario:
1. Agent writes SQL using string concatenation with user input.
2. User says: "Never concatenate SQL strings; always use parameterized queries."
3. Backend ingests/stores this conversation.
4. Backend suggests updating existing `db-access` skill.
5. Terminal shows notification: suggested existing skill with path.

Fallback:
- If no existing skill matches, backend suggests creating a new skill.

## 7. Non-Functional Requirements

- Endpoint response in under 2 seconds for normal local demo traffic.
- Keep demo resilient with local in-memory storage only.
- Keep response format stable for terminal notification logic.

## 8. Acceptance Criteria

- Ingestion endpoint accepts multi-event requests and stores them.
- Session history can be used for suggestion logic.
- Responses follow exactly one of: `ok`, `suggested_existing_skill`, `suggested_new_skill`.
- Demo can show at least one existing-skill suggestion and one new-skill suggestion.
