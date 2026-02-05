# Vibe Skilling - Product Requirements Document (Hackathon)

## 1. Overview

Vibe Skilling is an app that improves Codex project behavior over time by learning from past coding conversations and team communication.

The system analyzes exported conversation history (Codex CLI/App + Slack-like team chat exports) and proposes improvements to:
- `AGENTS.md`
- local skills (`SKILL.md`-style workflows)

For hackathon scope, ingestion is file-export based (not live APIs), and schema strictness is intentionally minimized so teams can move fast.

## 2. Problem

Teams repeatedly re-teach their coding agent the same constraints, conventions, and workflows. Valuable guidance is buried in:
- Codex conversation history
- team discussions (Slack/WhatsApp/etc.)

Without a feedback loop, the agent does not systematically improve project memory (`AGENTS.md`) and reusable skills.

## 3. Goal

Show an end-to-end Codex-powered workflow where team knowledge is converted into better agent instructions and skills, then validated with measurable task improvement.

## 4. Non-Goals (Hackathon)

- Production-grade real-time chat connectors
- Strict universal ingestion schema across all platforms
- Fully autonomous merge to `main` without human review
- Enterprise governance/compliance system

## 5. Users

- Primary: hackathon developers using Codex to build software
- Secondary: engineering teams that want shared, evolving project memory

## 6. Success Criteria

### Product success (during demo)

- Generate at least one meaningful `AGENTS.md` improvement proposal
- Generate at least one skill proposal from conversation patterns
- Show before/after impact on a concrete developer task

### Hackathon judging alignment

1. Impact:
- Clear developer pain solved (repeated prompting and lost team context)
- Reusable in any repo using Codex + team chat

2. Codex app story:
- Show Codex doing parallel analysis + patch generation + validation
- Use worktrees/parallel agents for visible end-to-end execution

3. Creative use of skills:
- Skill generation from real team history (not hand-written static skill)
- Include coding and non-technical technical workflows (e.g. triage/runbook)

4. Demo & pitch:
- Demonstrable artifact changes (`AGENTS.md`, skill files)
- Quantified improvement in short benchmark run

## 7. Core User Flow

1. User uploads/points to exported conversation files.
2. Ingestion normalizes text into lightweight internal records.
3. Analyzer identifies repeated friction patterns:
- repeated corrections
- recurring instructions
- task failures and retries
4. Proposal engine creates candidate updates for:
- `AGENTS.md`
- skill file(s)
5. Validator runs benchmark tasks in parallel worktrees:
- baseline config vs improved config
6. App shows diff + score + recommendation.
7. User accepts and exports PR-ready patch.

## 8. Functional Requirements

### FR-1 Ingestion (Hackathon Simplified)

- Accept local exported files from:
- Codex conversation history export
- Slack-like conversation export (or OpenClaw-provided equivalent export)
- Supported formats for MVP:
- `.txt`, `.md`, `.json`
- Minimal required fields after normalization:
- `source`
- `timestamp` (best effort)
- `speaker`
- `message`
- If timestamp/speaker missing, ingest should still proceed with best-effort parsing.

### FR-2 Pattern Extraction

- Detect recurring instructions and corrections
- Detect repeated task failure/retry loops
- Rank candidate insights by frequency and confidence

### FR-3 AGENTS.md Improvement Proposals

- Generate candidate instruction blocks with rationale
- Output as patch/diff against existing `AGENTS.md`
- Include confidence score and evidence references

### FR-4 Skill Proposals

- Generate at least one reusable skill draft from detected patterns
- Include:
- purpose
- trigger conditions
- execution steps
- expected outputs

### FR-5 Evaluation Harness

- Run a small task suite against baseline and improved configs
- Capture basic metrics:
- completion success/failure
- retries
- elapsed time

### FR-6 Review & Export

- Show side-by-side diff and metric deltas
- Export accepted changes as files/patch for PR submission

## 9. Non-Functional Requirements

- Must run locally during hackathon timeframe
- Must be fully open source
- Must complete end-to-end demo cycle in under 2 minutes runtime
- Must support partial/dirty input data without crashing

## 10. Technical Scope (Current FE/BE)

### Backend (FastAPI)

Current status:
- Minimal API scaffold with `/health`

Required additions:
- `POST /ingest`
- `POST /analyze`
- `POST /propose`
- `POST /evaluate`
- `GET /report/:id` (or equivalent)

### Frontend (React + Vite)

Current status:
- Starter counter UI

Required additions:
- data upload/import view
- pipeline status view (ingest -> analyze -> propose -> evaluate)
- diff/recommendation report view
- demo mode with preloaded sample datasets

## 11. Data Model (Flexible by design)

Internal normalized record (conceptual):

```json
{
  "source": "codex|slack|other",
  "timestamp": "optional",
  "speaker": "optional",
  "message": "string",
  "conversation_id": "optional"
}
```

Note: In hackathon scope, exact external schema mapping is not a blocker. Best-effort adapters are acceptable.

## 12. Demo Plan (3 min + 2 min Q&A)

### 3-minute demo script

1. Problem setup (20s)
- Show messy conversation exports and repeated prompt friction.

2. Ingestion + analysis (45s)
- Upload Codex + Slack-like exports.
- Show detected recurring patterns.

3. Improvement generation (45s)
- Show proposed `AGENTS.md` diff and generated skill draft.

4. Validation (45s)
- Run quick baseline vs improved benchmark in parallel.
- Show metric delta.

5. Close (25s)
- "Team knowledge becomes agent memory and reusable skills."

### 2-minute Q&A preparation topics

- Why export-based ingestion first (speed, reliability, hackathon constraints)
- How to add live connectors post-hackathon
- Safety controls (human-in-the-loop review before merge)
- Generalization to any engineering team

## 13. Risks and Mitigations

- Noisy chat data leads to low-quality suggestions
- Mitigation: confidence scoring + evidence snippets + manual approval

- Over-scoped ingestion work consumes build time
- Mitigation: strict export-first approach and minimal normalization

- Weak proof of impact in demo
- Mitigation: predefine a benchmark task set and report before/after metrics

## 14. Milestones (Hackathon Day)

1. Foundation (Hour 1)
- Create ingestion endpoint + file parser stubs
- Replace FE starter with pipeline shell

2. Intelligence (Hours 2-3)
- Implement pattern extraction + proposal generation

3. Evaluation (Hour 4)
- Implement quick benchmark harness and score output

4. Demo hardening (Hours 5+)
- Polish UI flow, prepare sample exports, rehearse timing

## 15. Acceptance Criteria

- App ingests at least two exported data sources
- App produces `AGENTS.md` proposal diff
- App produces at least one skill proposal
- App runs baseline vs improved evaluation and reports delta
- Demo fits 3 minutes with visible end-to-end flow
