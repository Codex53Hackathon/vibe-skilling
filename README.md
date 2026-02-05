# Vibe Skilling

Vibe Skilling is a hackathon project that turns team conversation history into better Codex guidance over time. It analyzes exported coding/chat conversations and proposes concrete improvements to project memory (`AGENTS.md`) and reusable skills (`SKILL.md` workflows).

## Why

Teams repeatedly restate the same constraints and workflows to coding agents. That guidance often lives in past Codex sessions and team chat exports, but is rarely converted into reusable project instructions.

Vibe Skilling closes that loop by:
- ingesting exported conversations,
- detecting repeated corrections and friction patterns,
- proposing updates to `AGENTS.md` and skills,
- validating improvements with baseline vs improved task runs.

## Hackathon Scope

- Export-based ingestion only (`.txt`, `.md`, `.json`)
- Best-effort normalization (tolerates missing speaker/timestamps)
- Human-in-the-loop review before applying suggestions
- End-to-end demo runtime target: under 2 minutes

## Product Flow

1. Upload or point to conversation export files.
2. Normalize data into lightweight internal records.
3. Analyze recurring instructions, retries, and failures.
4. Generate proposal diffs for `AGENTS.md` and new skills.
5. Run baseline vs improved evaluations on a small task suite.
6. Show diff + metric deltas + recommendation.
7. Export accepted changes as PR-ready patches/files.

## Repository Layout

- `/frontend` React + Vite UI
- `/backend` FastAPI API
- `/PRD.md` hackathon product requirements
- `/render.yaml` deployment configuration

## Current Status

Implemented:
- Backend scaffold with `GET /health`
- Frontend starter app

Planned core endpoints:
- `POST /ingest`
- `POST /analyze`
- `POST /propose`
- `POST /evaluate`
- `GET /report/:id` (or equivalent)

## Local Development

### Backend (FastAPI)

From `/backend`:

```bash
python3 -m pip install -e ".[dev]"
uvicorn backend.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

### Frontend (React + Vite)

From `/frontend`:

```bash
npm install
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173).

## Success Criteria (Demo)

- Produce at least one meaningful `AGENTS.md` proposal diff
- Produce at least one reusable skill proposal
- Show measurable before/after impact on a concrete developer task
- Fit the full demo in 3 minutes

## License

Open source project for hackathon use.
