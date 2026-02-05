from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.codex.codex_headless import find_repo_root
from backend.codex.orchestrator import RunMode, orchestrator, orchestrator_root

router = APIRouter(prefix="/codex")


class InsightsRunRequest(BaseModel):
    session_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    mode: RunMode = "fork"
    workdir: str | None = None
    model: str | None = None


class InsightsRunResponse(BaseModel):
    job_id: str
    artifact_id: str


class InsightsArtifactSummary(BaseModel):
    artifact_id: str
    created_at: str | None
    markdown_path: str
    json_path: str


class InsightsArtifactResponse(BaseModel):
    artifact_id: str
    session_id: str
    created_at: str | None = None
    markdown: str | None = None
    json: dict[str, Any] | None = None


class ProposalRunRequest(BaseModel):
    session_id: str = Field(min_length=1)
    insight_artifact_id: str = Field(min_length=1)
    prompt: str | None = None
    mode: RunMode = "fork"
    workdir: str | None = None
    model: str | None = None


class ProposalRunResponse(BaseModel):
    job_id: str
    proposal_id: str


class ProposalResponse(BaseModel):
    proposal_id: str
    session_id: str
    status: Literal["missing", "ready"]
    diff: str | None = None
    summary: str | None = None
    files_touched: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class ApplyResponse(BaseModel):
    applied: bool
    files_touched: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ApplyRequest(BaseModel):
    confirm: bool = False


def _find_insight_paths(repo_root: Path, session_id: str, artifact_id: str) -> tuple[Path | None, Path | None]:
    base = repo_root / ".codex-orchestrator" / "insights" / session_id
    if not base.exists():
        return None, None
    md = next(base.glob(f"*-{artifact_id}.md"), None)
    js = next(base.glob(f"*-{artifact_id}.json"), None)
    return md, js


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@router.post("/insights/run", response_model=InsightsRunResponse)
async def run_insights(req: InsightsRunRequest) -> InsightsRunResponse:
    job, artifact = await orchestrator.start_insights_run(
        session_id=req.session_id,
        prompt=req.prompt,
        mode=req.mode,
        workdir=req.workdir,
        model=req.model,
    )
    return InsightsRunResponse(job_id=job.id, artifact_id=artifact.artifact_id)


@router.get("/insights/{session_id}", response_model=list[InsightsArtifactSummary])
async def list_insights(session_id: str) -> list[InsightsArtifactSummary]:
    repo_root = find_repo_root(Path.cwd())
    base = repo_root / ".codex-orchestrator" / "insights" / session_id
    if not base.exists():
        return []

    out: list[InsightsArtifactSummary] = []
    for js in sorted(base.glob("*.json"), reverse=True):
        stem = js.stem
        # We write files as: <timestamp>-<uuid>.json. Extract the uuid safely.
        artifact_id = stem[-36:] if len(stem) >= 36 else stem
        md = js.with_suffix(".md")
        out.append(
            InsightsArtifactSummary(
                artifact_id=artifact_id,
                created_at=None,
                markdown_path=str(md),
                json_path=str(js),
            )
        )
    return out


@router.get("/insights/artifacts/{session_id}/{artifact_id}", response_model=InsightsArtifactResponse)
async def get_insight(session_id: str, artifact_id: str) -> InsightsArtifactResponse:
    repo_root = find_repo_root(Path.cwd())
    md_path, js_path = _find_insight_paths(repo_root, session_id, artifact_id)
    if not md_path and not js_path:
        raise HTTPException(status_code=404, detail="Insight artifact not found")

    md = None
    if md_path and md_path.exists():
        md = md_path.read_text(encoding="utf-8")
    payload = _read_json(js_path) if js_path else None

    return InsightsArtifactResponse(
        artifact_id=artifact_id,
        session_id=session_id,
        markdown=md,
        json=payload,
    )


@router.post("/proposals/run", response_model=ProposalRunResponse)
async def run_proposal(req: ProposalRunRequest) -> ProposalRunResponse:
    repo_root = find_repo_root(Path.cwd())
    _, js_path = _find_insight_paths(repo_root, req.session_id, req.insight_artifact_id)
    if not js_path or not js_path.exists():
        raise HTTPException(status_code=404, detail="Insight JSON not found")

    insight = _read_json(js_path)
    if insight is None:
        raise HTTPException(status_code=400, detail="Insight JSON is invalid")

    job, artifact = await orchestrator.start_proposal_run(
        session_id=req.session_id,
        insight_json=insight,
        prompt=req.prompt,
        mode=req.mode,
        workdir=req.workdir,
        model=req.model,
    )
    return ProposalRunResponse(job_id=job.id, proposal_id=artifact.proposal_id)


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(proposal_id: str) -> ProposalResponse:
    repo_root = find_repo_root(Path.cwd())
    base = repo_root / ".codex-orchestrator" / "proposals" / proposal_id
    diff_path = base / "proposal.diff"
    meta_path = base / "meta.json"
    if not base.exists():
        raise HTTPException(status_code=404, detail="Proposal not found")

    meta = _read_json(meta_path) if meta_path.exists() else None
    session_id = meta.get("session_id") if isinstance(meta, dict) else None
    summary = meta.get("summary") if isinstance(meta, dict) else None

    if not diff_path.exists():
        return ProposalResponse(
            proposal_id=proposal_id,
            session_id=session_id or "",
            status="missing",
        )

    diff_text = diff_path.read_text(encoding="utf-8")
    ok, touched, errors = orchestrator.validate_diff_paths(diff_text)

    return ProposalResponse(
        proposal_id=proposal_id,
        session_id=session_id or "",
        status="ready",
        diff=diff_text,
        summary=summary,
        files_touched=touched if ok else touched,
        validation_errors=errors,
    )


@router.post("/proposals/{proposal_id}/apply", response_model=ApplyResponse)
async def apply_proposal(proposal_id: str, req: ApplyRequest) -> ApplyResponse:
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Missing confirmation")
    repo_root = find_repo_root(Path.cwd())
    diff_path = repo_root / ".codex-orchestrator" / "proposals" / proposal_id / "proposal.diff"
    if not diff_path.exists():
        raise HTTPException(status_code=404, detail="Proposal diff not found")

    result = orchestrator.apply_proposal_diff(diff_path=diff_path)
    return ApplyResponse(
        applied=bool(result.get("applied")),
        files_touched=list(result.get("files_touched") or []),
        errors=list(result.get("errors") or []),
    )


@router.get("/orchestrator/root")
async def get_orchestrator_root() -> dict[str, Any]:
    repo_root = find_repo_root(Path.cwd())
    return {"root": str(orchestrator_root(repo_root))}
