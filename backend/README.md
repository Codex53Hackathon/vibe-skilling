## FastAPI template

### Run (recommended)

From `backend/`:

1) Create/activate a venv (if you don't already have one)
2) Install deps + the package:
   - `python3 -m pip install -e ".[dev]"`
3) Start the server:
   - `uvicorn backend.main:app --reload`

### Run (no install)

From `backend/`:
- `python3 -m pip install fastapi pydantic-settings "uvicorn[standard]"`
- `uvicorn backend.main:app --reload --app-dir src`

### Endpoints

- `GET /health` -> `{ "status": "ok" }`
- `GET /codex/sessions` -> list Codex conversations (from `CODEX_HOME`)
- `GET /codex/sessions/{session_id}` -> fetch transcript
- `POST /codex/insights/run` -> run headless “insights” on a conversation
- `POST /codex/proposals/run` -> generate a diff proposing changes to `.codex/skills/**` + `AGENTS.md`
- `POST /codex/proposals/{proposal_id}/apply` -> apply an approved diff to the repo
- `GET /codex/jobs/{job_id}` -> poll job status + output tail
- `DELETE /codex/jobs/{job_id}` -> cancel a running job

### Headless Codex

Start the API:
```bash
uvicorn backend.main:app --reload
```

Before running headless jobs, make sure Codex is authenticated using the same `CODEX_HOME`
directory the backend will use (so it can find credentials + sessions):
```bash
export CODEX_HOME="$HOME/.codex"
codex login
```

Optional: start the minimal frontend (from `frontend/`):
```bash
npm install
npm run dev
```

Run an insights job:
```bash
curl -sS -X POST http://localhost:8000/codex/insights/run \
  -H 'content-type: application/json' \
  -d '{"session_id":"<session_id>","mode":"fork","prompt":"Summarize key learnings and propose skill improvements"}'
```

Then poll:
```bash
curl -sS http://localhost:8000/codex/jobs/<job_id>?tail=200
```
