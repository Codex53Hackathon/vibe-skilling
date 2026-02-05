from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.codex.codex_headless import ApprovalPolicy, SandboxMode, runner

router = APIRouter(prefix="/codex")


class CodexExecRequest(BaseModel):
    task: str = Field(min_length=1)
    workdir: str | None = None
    sandbox: SandboxMode = "workspace-write"
    approval: ApprovalPolicy = "never"
    model: str | None = None
    oss: bool = False
    local_provider: Literal["lmstudio", "ollama"] | None = None
    profile: str | None = None
    config_overrides: list[str] = Field(default_factory=list)
    output_schema_path: str | None = None
    skip_git_repo_check: bool = False
    max_output_lines: int = Field(default=2000, ge=100, le=20000)


class CodexJobResponse(BaseModel):
    id: str
    status: str
    returncode: int | None
    task_id: str | None
    command: list[str]
    codex_home: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    last_message: str | None
    stdout_tail: list[str]
    stderr_tail: list[str]
    events_tail: list[dict[str, Any]]


def _read_last_message(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


@router.post("/exec", response_model=CodexJobResponse)
async def codex_exec(req: CodexExecRequest) -> CodexJobResponse:
    job = await runner.create_job(
        task=req.task,
        workdir=req.workdir,
        sandbox=req.sandbox,
        approval=req.approval,
        model=req.model,
        oss=req.oss,
        local_provider=req.local_provider,
        profile=req.profile,
        config_overrides=req.config_overrides,
        output_schema_path=req.output_schema_path,
        skip_git_repo_check=req.skip_git_repo_check,
        max_output_lines=req.max_output_lines,
    )
    return CodexJobResponse(
        id=job.id,
        status=job.status,
        returncode=job.returncode,
        task_id=job.task_id,
        command=job.command,
        codex_home=str(job.codex_home),
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        last_message=_read_last_message(job.last_message_path),
        stdout_tail=list(job.stdout_lines),
        stderr_tail=list(job.stderr_lines),
        events_tail=list(job.events),
    )


@router.get("/jobs/{job_id}", response_model=CodexJobResponse)
async def codex_job(
    job_id: str,
    tail: int = Query(default=200, ge=1, le=2000),
) -> CodexJobResponse:
    job = await runner.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stdout_tail = list(job.stdout_lines)[-tail:]
    stderr_tail = list(job.stderr_lines)[-tail:]
    events_tail = list(job.events)[-tail:]

    return CodexJobResponse(
        id=job.id,
        status=job.status,
        returncode=job.returncode,
        task_id=job.task_id,
        command=job.command,
        codex_home=str(job.codex_home),
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        last_message=_read_last_message(job.last_message_path),
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        events_tail=events_tail,
    )


@router.delete("/jobs/{job_id}")
async def codex_cancel(job_id: str) -> dict[str, Any]:
    ok = await runner.cancel_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not running or not found")
    return {"status": "canceled", "id": job_id}
