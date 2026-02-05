from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from backend.codex.codex_headless import CodexJob, find_repo_root, resolve_codex_home, runner
from backend.codex.history import read_session_messages, render_transcript

RunMode = Literal["fork", "resume"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def orchestrator_root(repo_root: Path) -> Path:
    return (repo_root / ".codex-orchestrator").resolve()


def insights_dir(repo_root: Path, session_id: str) -> Path:
    return orchestrator_root(repo_root) / "insights" / session_id


def proposals_dir(repo_root: Path, proposal_id: str) -> Path:
    return orchestrator_root(repo_root) / "proposals" / proposal_id


def runs_dir(repo_root: Path) -> Path:
    return orchestrator_root(repo_root) / "runs"


def _timestamp_slug(dt: datetime | None = None) -> str:
    dt = dt or _utc_now()
    return dt.strftime("%Y%m%d-%H%M%SZ")


def _schemas_dir(repo_root: Path) -> Path:
    return repo_root / "backend" / "src" / "backend" / "codex" / "schemas"


def insights_schema_path(repo_root: Path) -> Path:
    return _schemas_dir(repo_root) / "insights.schema.json"


def proposal_schema_path(repo_root: Path) -> Path:
    return _schemas_dir(repo_root) / "proposal.schema.json"


@dataclass(frozen=True, slots=True)
class InsightsArtifact:
    artifact_id: str
    session_id: str
    markdown_path: Path
    json_path: Path
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProposalArtifact:
    proposal_id: str
    session_id: str
    diff_path: Path
    meta_path: Path
    created_at: datetime


class Orchestrator:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._job_to_insights: dict[str, InsightsArtifact] = {}
        self._job_to_proposal: dict[str, ProposalArtifact] = {}

    async def start_insights_run(
        self,
        *,
        session_id: str,
        prompt: str,
        mode: RunMode,
        workdir: str | None = None,
        model: str | None = None,
    ) -> tuple[CodexJob, InsightsArtifact]:
        repo_root = find_repo_root(Path.cwd())
        out_dir = insights_dir(repo_root, session_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        artifact_id = str(uuid4())
        slug = _timestamp_slug()
        md_path = out_dir / f"{slug}-{artifact_id}.md"
        json_path = out_dir / f"{slug}-{artifact_id}.json"

        artifact = InsightsArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            markdown_path=md_path,
            json_path=json_path,
            created_at=_utc_now(),
        )

        schema = insights_schema_path(repo_root)
        task = self._build_insights_task(repo_root=repo_root, session_id=session_id, prompt=prompt, mode=mode)

        job = await runner.create_job(
            task=task,
            workdir=workdir,
            sandbox="read-only",
            approval="never",
            model=model,
            output_schema_path=str(schema),
            resume_session_id=session_id if mode == "resume" else None,
        )

        async with self._lock:
            self._job_to_insights[job.id] = artifact

        self._persist_run_meta(repo_root, job, kind="insights", outputs={"artifact_id": artifact_id})
        asyncio.create_task(self._finalize_insights(repo_root, job.id))
        return job, artifact

    async def start_proposal_run(
        self,
        *,
        session_id: str,
        insight_json: dict[str, Any],
        prompt: str | None,
        mode: RunMode,
        workdir: str | None = None,
        model: str | None = None,
    ) -> tuple[CodexJob, ProposalArtifact]:
        repo_root = find_repo_root(Path.cwd())

        proposal_id = str(uuid4())
        out_dir = proposals_dir(repo_root, proposal_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        diff_path = out_dir / "proposal.diff"
        meta_path = out_dir / "meta.json"

        artifact = ProposalArtifact(
            proposal_id=proposal_id,
            session_id=session_id,
            diff_path=diff_path,
            meta_path=meta_path,
            created_at=_utc_now(),
        )

        schema = proposal_schema_path(repo_root)
        task = self._build_proposal_task(
            repo_root=repo_root,
            session_id=session_id,
            insight=insight_json,
            prompt=prompt,
            mode=mode,
        )

        job = await runner.create_job(
            task=task,
            workdir=workdir,
            sandbox="read-only",
            approval="never",
            model=model,
            output_schema_path=str(schema),
            resume_session_id=session_id if mode == "resume" else None,
        )

        async with self._lock:
            self._job_to_proposal[job.id] = artifact

        self._persist_run_meta(repo_root, job, kind="proposal", outputs={"proposal_id": proposal_id})
        asyncio.create_task(self._finalize_proposal(repo_root, job.id))
        return job, artifact

    async def get_insights_artifact_for_job(self, job_id: str) -> InsightsArtifact | None:
        async with self._lock:
            return self._job_to_insights.get(job_id)

    async def get_proposal_artifact_for_job(self, job_id: str) -> ProposalArtifact | None:
        async with self._lock:
            return self._job_to_proposal.get(job_id)

    def _persist_run_meta(self, repo_root: Path, job: CodexJob, *, kind: str, outputs: dict[str, Any]) -> None:
        out = runs_dir(repo_root)
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            "job_id": job.id,
            "kind": kind,
            "created_at": job.created_at.isoformat(),
            "command": job.command,
            "workdir": str(job.cwd),
            "codex_home": str(job.codex_home),
            "outputs": outputs,
        }
        (out / f"{job.id}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _build_insights_task(self, *, repo_root: Path, session_id: str, prompt: str, mode: RunMode) -> str:
        base = [
            "You are generating *insights* to help improve this repository’s Codex skills and AGENTS.md.",
            "Return ONLY a JSON object matching the provided output schema.",
        ]
        if mode == "fork":
            messages = read_session_messages(resolve_codex_home(repo_root), session_id)
            transcript = render_transcript(messages)
            if transcript:
                base += ["", "Conversation transcript:", transcript]
        base += ["", "User prompt:", prompt.strip()]
        return "\n".join(base).strip() + "\n"

    def _build_proposal_task(
        self,
        *,
        repo_root: Path,
        session_id: str,
        insight: dict[str, Any],
        prompt: str | None,
        mode: RunMode,
    ) -> str:
        base = [
            "You are proposing changes to make Codex more effective on this repository.",
            "You MUST output a unified diff in the `diff` field of the JSON schema.",
            "Allowed paths: `.codex/skills/**` and `AGENTS.md` only.",
            "Return ONLY a JSON object matching the provided output schema.",
            "",
            "Insights (JSON):",
            json.dumps(insight, indent=2, sort_keys=True)[:50_000],
        ]
        if mode == "fork":
            messages = read_session_messages(resolve_codex_home(repo_root), session_id)
            transcript = render_transcript(messages)
            if transcript:
                base += ["", "Conversation transcript:", transcript]
        if prompt:
            base += ["", "Additional user prompt:", prompt.strip()]
        return "\n".join(base).strip() + "\n"

    async def _finalize_insights(self, repo_root: Path, job_id: str) -> None:
        artifact = await self.get_insights_artifact_for_job(job_id)
        if not artifact:
            return

        while True:
            job = await runner.get_job(job_id)
            if not job:
                return
            if job.status not in ("queued", "running"):
                break
            await asyncio.sleep(0.25)

        job = await runner.get_job(job_id)
        if not job or job.status != "succeeded":
            return

        raw = artifact.json_path
        md = artifact.markdown_path

        last = _read_last_message(job.last_message_path)
        if not last:
            return
        try:
            payload = json.loads(last)
        except json.JSONDecodeError:
            return

        raw.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        md_text = payload.get("insights_markdown") if isinstance(payload, dict) else None
        if isinstance(md_text, str) and md_text.strip():
            md.write_text(md_text.strip() + "\n", encoding="utf-8")

    async def _finalize_proposal(self, repo_root: Path, job_id: str) -> None:
        artifact = await self.get_proposal_artifact_for_job(job_id)
        if not artifact:
            return

        while True:
            job = await runner.get_job(job_id)
            if not job:
                return
            if job.status not in ("queued", "running"):
                break
            await asyncio.sleep(0.25)

        job = await runner.get_job(job_id)
        if not job or job.status != "succeeded":
            return

        last = _read_last_message(job.last_message_path)
        if not last:
            return
        try:
            payload = json.loads(last)
        except json.JSONDecodeError:
            return

        diff = payload.get("diff") if isinstance(payload, dict) else None
        if not isinstance(diff, str) or not diff.strip():
            return

        artifact.diff_path.write_text(diff.strip() + "\n", encoding="utf-8")
        meta = {
            "proposal_id": artifact.proposal_id,
            "session_id": artifact.session_id,
            "created_at": artifact.created_at.isoformat(),
            "job_id": job_id,
            "summary": payload.get("summary") if isinstance(payload, dict) else None,
            "files_touched": payload.get("files_touched") if isinstance(payload, dict) else None,
            "safety_notes": payload.get("safety_notes") if isinstance(payload, dict) else None,
        }
        artifact.meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def validate_diff_paths(self, diff_text: str) -> tuple[bool, list[str], list[str]]:
        """
        Returns: (ok, touched_paths, errors)
        """
        touched: set[str] = set()
        errors: list[str] = []

        for line in diff_text.splitlines():
            if line.startswith("+++ ") or line.startswith("--- "):
                parts = line.split()
                if len(parts) < 2:
                    continue
                path = parts[1]
                if path in ("a/dev/null", "b/dev/null", "/dev/null"):
                    continue
                if path.startswith("a/") or path.startswith("b/"):
                    path = path[2:]
                touched.add(path)

        if not touched:
            errors.append("No file paths detected in diff.")

        for path in sorted(touched):
            if path == "AGENTS.md" or path.endswith("/AGENTS.md"):
                continue
            if path.startswith(".codex/skills/"):
                continue
            errors.append(f"Disallowed path in diff: {path}")

        return (len(errors) == 0, sorted(touched), errors)

    def apply_proposal_diff(self, *, diff_path: Path) -> dict[str, Any]:
        repo_root = find_repo_root(Path.cwd())
        diff_text = diff_path.read_text(encoding="utf-8")
        ok, touched, errors = self.validate_diff_paths(diff_text)
        if not ok:
            return {"applied": False, "errors": errors, "files_touched": touched}

        proc = subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(diff_path)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return {
                "applied": False,
                "errors": ["git apply failed", proc.stderr.strip() or proc.stdout.strip() or "unknown error"],
                "files_touched": touched,
            }
        return {"applied": True, "files_touched": touched}


def _read_last_message(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


orchestrator = Orchestrator()
