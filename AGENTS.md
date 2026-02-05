# AGENTS.md

## Purpose
This repository is deployed to Render and contains two services:
- `vibe-skilling-api` (Python web service from `backend/`)
- `vibe-skilling-web` (static site from `frontend/`)

Use this file as the default runbook for deployment-related agent tasks.

## Deployment Model
- Primary: Render direct-created services (already provisioned in workspace `tea-d5v4eq94tr6s739e2bh0`)
- Secondary/fallback: Blueprint via `/render.yaml`

`render.yaml` is kept for reproducibility and one-click recreation, but active production deploys currently happen through the existing direct-created services.

## Render Service Configuration

### API service
- Name: `vibe-skilling-api`
- Service ID: `srv-d62gfv1r0fns73bhtb6g`
- Type: `web_service`
- URL: `https://vibe-skilling-api.onrender.com`
- Build command: `cd backend && pip install .`
- Start command: `cd backend && uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Env vars:
  - `APP_APP_NAME=Backend API`

### Frontend service
- Name: `vibe-skilling-web`
- Service ID: `srv-d62gfunpm1nc73dvhgc0`
- Type: `static_site`
- URL: `https://vibe-skilling-web.onrender.com`
- Build command: `cd frontend && npm ci && npm run build`
- Publish path: `frontend/dist`
- Env vars:
  - `VITE_API_URL=https://vibe-skilling-api.onrender.com`

## Important Constraints
- `frontend/package-lock.json` must exist because Render build uses `npm ci`.
- Keep API externally reachable for frontend usage.
- For API web services on Render, always bind to `0.0.0.0:$PORT`.

## Standard Agent Checks After Any Deploy Change
1. Verify latest deploy status is `live` for both services.
2. Verify API health endpoint: `GET /health` returns `200`.
3. Verify frontend URL loads and can reach API URL configured in `VITE_API_URL`.
4. Scan recent logs for `error` level entries.

## MCP Prerequisites
- Render MCP server must be configured with bearer token env var.
- Preferred repo-shared setup:
  - `bash scripts/setup-codex-render-mcp.sh`
- Manual equivalent:
  - `codex mcp add render --url https://mcp.render.com/mcp --bearer-token-env-var RENDER_API_KEY`
- Session must have `RENDER_API_KEY` set.
- Workspace must be selected before actions:
  - `tea-d5v4eq94tr6s739e2bh0`
