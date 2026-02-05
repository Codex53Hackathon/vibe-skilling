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
- `/AGENTS.md` agent runbook and deployment instructions
- `/scripts/setup-codex-render-mcp.sh` teammate setup for Codex Render MCP

## Render Deployment (Current)

This project is currently deployed with **Render direct-created services** (via MCP), and also includes `render.yaml` as Infrastructure-as-Code fallback.

### Active services

- API: `vibe-skilling-api`
  - URL: [https://vibe-skilling-api.onrender.com](https://vibe-skilling-api.onrender.com)
  - Build: `cd backend && pip install .`
  - Start: `cd backend && uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
  - Env vars: `APP_APP_NAME=Backend API`

- Frontend: `vibe-skilling-web`
  - URL: [https://vibe-skilling-web.onrender.com](https://vibe-skilling-web.onrender.com)
  - Build: `cd frontend && npm ci && npm run build`
  - Publish path: `frontend/dist`
  - Env vars: `VITE_API_URL=https://vibe-skilling-api.onrender.com`

### Do we need `render.yaml`?

Not strictly for the already-created direct services. Those keep auto-deploying from `main` as configured in Render.

We still keep `render.yaml` because it is useful for:
- reproducible re-creation of infra,
- sharing deployment config in Git,
- one-click Blueprint setup in a new workspace/account.

### How deployment is working

1. Push code to `main`.
2. Render auto-deploy triggers for both services.
3. API runs from `backend/`; frontend builds from `frontend/`.
4. Frontend uses `VITE_API_URL` pointing to the API service URL.

Note: `frontend/package-lock.json` is required because build uses `npm ci`.

### Codex MCP setup for teammates

Codex stores MCP servers in user-global config (`~/.codex/config.toml`), not directly in repo files.  
This repo provides a shared setup script so teammates can apply the same config consistently.

```bash
export RENDER_API_KEY="rnd_..."
bash scripts/setup-codex-render-mcp.sh
```

After running:
1. Restart Codex.
2. Select Render workspace in chat:
   - `Set my Render workspace to tea-d5v4eq94tr6s739e2bh0`

### Quick verification

```bash
curl -i https://vibe-skilling-api.onrender.com/health
```

Expected: HTTP `200` and `{"status":"ok"}`.

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
