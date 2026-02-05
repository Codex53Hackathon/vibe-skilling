from __future__ import annotations

import asyncio
import json
import os
import signal
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Literal
from uuid import uuid4

SandboxMode = Literal["read-only", "workspace-write", "danger-full-access"]
ApprovalPolicy = Literal["untrusted", "on-failure", "on-request", "never"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def find_repo_root(start: Path) -> Path:
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


def _resolve_workdir(repo_root: Path, workdir: str | None) -> Path:
    if not workdir:
        return repo_root
    p = Path(workdir)
    if p.is_absolute():
        return p
    return (repo_root / p).resolve()


def resolve_codex_home(repo_root: Path) -> Path:
    """
    Stable CODEX_HOME root used for both:
    - reading Codex conversation history (sessions)
    - running headless Codex jobs (auth lives here)
    """
    raw = os.getenv("CODEX_HOME")
    if not raw:
        return (Path.home() / ".codex").resolve()
    p = Path(raw)
    return (p if p.is_absolute() else repo_root / p).expanduser().resolve()


def _extract_task_id(event: Any) -> str | None:
    if isinstance(event, dict):
        for key in ("task_id", "taskId", "taskID"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in event.values():
            task_id = _extract_task_id(value)
            if task_id:
                return task_id
    elif isinstance(event, list):
        for value in event:
            task_id = _extract_task_id(value)
            if task_id:
                return task_id
    return None


@dataclass(slots=True)
class CodexJob:
    id: str
    task: str
    command: list[str]
    cwd: Path
    codex_home: Path
    job_dir: Path
    last_message_path: Path
    created_at: datetime = field(default_factory=_utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: Literal["queued", "running", "succeeded", "failed", "canceled"] = "queued"
    returncode: int | None = None
    task_id: str | None = None
    stdout_lines: Deque[str] = field(default_factory=lambda: deque(maxlen=2000))
    stderr_lines: Deque[str] = field(default_factory=lambda: deque(maxlen=2000))
    events: Deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=2000))
    _process: asyncio.subprocess.Process | None = None


class CodexHeadlessRunner:
    def __init__(self) -> None:
        self._jobs: dict[str, CodexJob] = {}
        self._lock = asyncio.Lock()

    async def create_job(
        self,
        *,
        task: str,
        workdir: str | None = None,
        sandbox: SandboxMode = "workspace-write",
        approval: ApprovalPolicy = "never",
        model: str | None = None,
        oss: bool = False,
        local_provider: Literal["lmstudio", "ollama"] | None = None,
        profile: str | None = None,
        config_overrides: list[str] | None = None,
        output_schema_path: str | None = None,
        skip_git_repo_check: bool = False,
        max_output_lines: int = 2000,
        resume_session_id: str | None = None,
    ) -> CodexJob:
        repo_root = find_repo_root(Path.cwd())
        resolved_workdir = _resolve_workdir(repo_root, workdir)

        job_id = str(uuid4())
        codex_home = resolve_codex_home(repo_root)
        codex_home.mkdir(parents=True, exist_ok=True)

        job_dir = codex_home / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        last_message_path = job_dir / "last_message.txt"

        command = self._build_command(
            approval=approval,
            sandbox=sandbox,
            workdir=resolved_workdir,
            last_message_path=last_message_path,
            model=model,
            oss=oss,
            local_provider=local_provider,
            profile=profile,
            config_overrides=config_overrides or [],
            output_schema_path=output_schema_path,
            skip_git_repo_check=skip_git_repo_check,
            resume_session_id=resume_session_id,
        )

        job = CodexJob(
            id=job_id,
            task=task,
            command=command,
            cwd=repo_root,
            codex_home=codex_home,
            job_dir=job_dir,
            last_message_path=last_message_path,
            stdout_lines=deque(maxlen=max_output_lines),
            stderr_lines=deque(maxlen=max_output_lines),
            events=deque(maxlen=max_output_lines),
        )

        async with self._lock:
            self._jobs[job_id] = job

        asyncio.create_task(self._run_job(job_id))
        return job

    async def get_job(self, job_id: str) -> CodexJob | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            process = job._process
            if not process or job.status not in ("queued", "running"):
                return False
            job.status = "canceled"

        try:
            process.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            pass
        return True

    def _build_command(
        self,
        *,
        approval: ApprovalPolicy,
        sandbox: SandboxMode,
        workdir: Path,
        last_message_path: Path,
        model: str | None,
        oss: bool,
        local_provider: Literal["lmstudio", "ollama"] | None,
        profile: str | None,
        config_overrides: list[str],
        output_schema_path: str | None,
        skip_git_repo_check: bool,
        resume_session_id: str | None,
    ) -> list[str]:
        cmd: list[str] = ["codex", "--no-alt-screen"]
        cmd += ["--ask-for-approval", approval]
        cmd += ["--sandbox", sandbox]
        if model:
            cmd += ["--model", model]
        if oss:
            cmd += ["--oss"]
        if local_provider:
            cmd += ["--local-provider", local_provider]
        if profile:
            cmd += ["--profile", profile]
        for override in config_overrides:
            cmd += ["-c", override]

        if resume_session_id:
            cmd += [
                "exec",
                "resume",
                "--json",
                "-C",
                str(workdir),
                "-o",
                str(last_message_path),
            ]
            if output_schema_path:
                cmd += ["--output-schema", output_schema_path]
            if skip_git_repo_check:
                cmd += ["--skip-git-repo-check"]
            cmd += [resume_session_id, "-"]
            return cmd

        cmd += [
            "exec",
            "--json",
            "-C",
            str(workdir),
            "-o",
            str(last_message_path),
        ]
        if output_schema_path:
            cmd += ["--output-schema", output_schema_path]
        if skip_git_repo_check:
            cmd += ["--skip-git-repo-check"]
        cmd += ["-"]
        return cmd

    async def _run_job(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "queued":
                return
            job.status = "running"
            job.started_at = _utc_now()

        env = dict(os.environ)
        env["CODEX_HOME"] = str(job.codex_home)

        process = await asyncio.create_subprocess_exec(
            *job.command,
            cwd=str(job.cwd),
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async with self._lock:
            job._process = process

        assert process.stdin is not None
        process.stdin.write(job.task.encode("utf-8"))
        process.stdin.write(b"\n")
        await process.stdin.drain()
        process.stdin.close()

        async def read_stream(
            stream: asyncio.StreamReader,
            sink: Deque[str],
            *,
            parse_json: bool,
        ) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    return
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                sink.append(text)
                if parse_json:
                    try:
                        event = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        job.events.append(event)
                        if not job.task_id:
                            job.task_id = _extract_task_id(event)

        assert process.stdout is not None
        assert process.stderr is not None
        await asyncio.gather(
            read_stream(process.stdout, job.stdout_lines, parse_json=True),
            read_stream(process.stderr, job.stderr_lines, parse_json=False),
        )

        returncode = await process.wait()

        async with self._lock:
            job.returncode = returncode
            job.finished_at = _utc_now()
            if job.status == "canceled":
                return
            job.status = "succeeded" if returncode == 0 else "failed"


runner = CodexHeadlessRunner()
