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
