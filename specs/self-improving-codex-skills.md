# Spec: Self‑Improving Codex Skills (Human‑in‑the‑Loop)

## 1) Goal
Build a minimal web UI + backend workflow that:
1) Lets a user browse/select Codex conversation history.
2) Runs Codex headlessly with a prompt grounded in the selected conversation.
3) Saves “insights” to a predefined repo path and serves them to the frontend.
4) Runs a second headless Codex job to propose improvements to:
   - repo‑scoped skills under `./.codex/skills/**`
   - `./AGENTS.md` (and optionally subtree `AGENTS.md`)
5) Requires explicit human approval before writing any proposed changes into the repo.

Non‑goal: Replace the Codex UI; this is an orchestrator for “select history → run jobs → review → apply”.


## 2) Repo conventions (source of truth)
### 2.1 Repo‑scoped skills
All skills managed by this system are repo‑scoped and MUST live under:
- `REPO_ROOT/.codex/skills/<skill_name>/SKILL.md`
- optional: `scripts/`, `references/`, `assets/` under the same skill directory

The system MUST NOT propose changes outside `.codex/skills/**` and `AGENTS.md` unless the user explicitly opts in.

### 2.2 Orchestrator artifacts
The system stores run artifacts under:
- `REPO_ROOT/.codex-orchestrator/`
  - `insights/<session_id>/<timestamp>.md` and `<timestamp>.json`
  - `proposals/<proposal_id>/proposal.diff` and `meta.json`
  - `runs/<job_id>.json`


## 3) Headless execution (backend‑owned)
The backend runs Codex in headless mode using the existing runner implementation:
- `backend/src/backend/codex/headless.py`

### 3.1 Authentication and `CODEX_HOME`
Headless jobs MUST run with a stable `CODEX_HOME` that contains Codex auth state.
- Backend process sets `CODEX_HOME` to a stable directory (example: `REPO_ROOT/.codex-headless/`).
- Operator runs `codex login` once using that same `CODEX_HOME`.

Rationale: headless runs must be able to access credentials consistently.

### 3.2 Conversation continuity: resume vs fork
The system supports two ways to run prompts “based on conversation history”:
- **Fork (recommended default):** create a new session branched from the selected session, then run prompts in the fork. This preserves the original conversation and provides a clean audit trail.
- **Resume (optional):** continue the selected session in place (history grows).

The UI MUST make this choice explicit (default to Fork).


## 4) Conversation history access
### 4.1 Requirements
Frontend must display the selected conversation transcript.
Backend must provide:
- List of sessions: id, title/name (if available), timestamps, and a repo/cwd hint.
- Transcript for a session: ordered messages/events (role, content, timestamp).

### 4.2 Source of truth
Conversation history is read from the Codex session store under the backend’s configured `CODEX_HOME`.

### 4.3 Session store abstraction
Backend implements a `SessionStore` abstraction:
- `list_sessions() -> [SessionSummary]`
- `get_session(session_id) -> SessionDetail`

Implementation detail is intentionally deferred until format discovery is done:
- Discover and document the actual on‑disk format and fields under `${CODEX_HOME}/sessions`.
- If parsing is not feasible/reliable, define a fallback path (e.g., limited UI that accepts a session id and runs fork/resume without transcript rendering).


## 5) Workflows
### 5.1 Workflow A: Generate insights
Input:
- `session_id`
- `insights_prompt` (user editable; defaults provided)
- mode: `fork|resume`
- model / sandbox / approvals config

Execution:
- Run Codex headlessly with the selected conversation as context:
  - If `fork`: fork session, then run prompt in the fork.
  - If `resume`: resume session and run prompt.

Outputs:
- A structured insights JSON (validated by schema).
- A rendered markdown summary for display.

Storage:
- Write artifacts to `.codex-orchestrator/insights/<session_id>/...`

Frontend:
- Show job progress and display the rendered insights markdown on completion.

### 5.2 Workflow B: Propose skill + `AGENTS.md` changes (DIFF output)
Input:
- `session_id`
- `insight_artifact_id` (selected insights)
- mode: `fork|resume` (default fork)
- constraints:
  - allowed paths: `.codex/skills/**`, `AGENTS.md`
  - output type: `diff` (unified diff)

Execution:
- Run Codex headlessly in **read‑only** mode (cannot write to repo).
- Provide conversation transcript (or a normalized summary) + selected insights to the model.
- Require output schema that includes:
  - `diff` (unified diff text)
  - `summary`
  - `files_touched[]`
  - `safety_notes[]`

Outputs:
- Save `proposal.diff` and `meta.json` under `.codex-orchestrator/proposals/<proposal_id>/`.

Frontend:
- Display a diff viewer and a short summary.
- Provide “Approve & apply” button (disabled until validation passes and user confirms).

### 5.3 Workflow C: Apply approved changes (human‑in‑the‑loop)
Input:
- `proposal_id`
- explicit confirmation (checkbox + final confirm)

Backend validation MUST enforce:
- Patch only touches allowed paths.
- Max file sizes and total patch size limits.
- Denylist patterns (e.g., `.env*`, keys, credentials, binaries).
- No path traversal / absolute paths.

Apply:
- Apply `proposal.diff` to the working tree.
- Record audit in `.codex-orchestrator/proposals/<proposal_id>/meta.json` (applied_at, files_changed, validation results).

Non‑goal: automatic git commit (optional future enhancement).


## 6) Backend API (minimal)
### 6.1 Sessions
- `GET /codex/sessions`
  - returns: `[{ id, title, updated_at, repo_hint? }]`
- `GET /codex/sessions/{id}`
  - returns: `{ id, messages:[{ role, content, ts, kind }], metadata }`

### 6.2 Runs / jobs
Use existing job status pattern:
- `GET /codex/jobs/{job_id}?tail=N`

### 6.3 Insights
- `POST /codex/insights/run`
  - body: `{ session_id, prompt, mode, model?, sandbox?, approval? }`
  - returns: `{ job_id, insight_artifact_id? }`
- `GET /codex/insights/{session_id}`
  - returns: list of artifacts + metadata
- `GET /codex/insights/artifacts/{artifact_id}`
  - returns: markdown/json

### 6.4 Proposals (diff)
- `POST /codex/proposals/run`
  - body: `{ session_id, insight_artifact_id, prompt?, mode }`
  - returns: `{ job_id, proposal_id? }`
- `GET /codex/proposals/{proposal_id}`
  - returns: `{ status, diff, summary, files_touched, validation }`
- `POST /codex/proposals/{proposal_id}/apply`
  - body: `{ confirm: true }`
  - returns: `{ applied: true, files_changed: [...] }`


## 7) Frontend UX (minimalistic)
Single page layout:
- **Left:** Session list (search + select)
- **Center:** Transcript viewer (read‑only)
- **Right:** Actions
  - Insights: prompt box + “Run” + render markdown output
  - Proposals: “Generate diff” + diff viewer + “Approve & apply”

UI requirements:
- Must show which session is selected.
- Must show whether the run is fork or resume (default fork).
- Must clearly separate “proposal generated” from “proposal applied”.


## 8) Safety and guardrails
- Backend never exposes secrets (API keys, tokens) to frontend.
- All Codex runs are recorded with: session_id, prompts, model/config, timestamps, job_id, codex task id (if available).
- Proposal apply is strictly validated and path‑restricted.
- Default sandbox levels:
  - Insights: `workspace-write` (optional; but prefer read‑only if writing is not needed).
  - Proposal generation: `read-only`.
  - Apply: performed by backend, not by Codex.


## 9) Open questions / decisions needed
1) Session store format discovery: document `${CODEX_HOME}/sessions` structure and implement parsing.
2) Transcript fidelity: do we display “assistant/tool events” or only user/assistant messages?
3) Fork implementation details: how to programmatically fork via Codex CLI in a headless/non‑interactive way and capture new session id.
4) Validation limits: patch size limits and allowed file count thresholds.

