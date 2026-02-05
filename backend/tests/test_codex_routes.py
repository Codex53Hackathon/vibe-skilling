from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.main import app


def test_codex_exec_creates_job(monkeypatch) -> None:
    now = datetime(2026, 2, 5, tzinfo=timezone.utc)
    fake_job = SimpleNamespace(
        id="job-123",
        status="queued",
        returncode=None,
        task_id=None,
        command=["codex", "exec", "--json", "-"],
        codex_home="/tmp/codex-home/job-123",
        created_at=now,
        started_at=None,
        finished_at=None,
        last_message_path=SimpleNamespace(read_text=lambda **_: "done"),
        stdout_lines=deque(["{}"], maxlen=2000),
        stderr_lines=deque([], maxlen=2000),
        events=deque([{"type": "noop"}], maxlen=2000),
    )

    async def fake_create_job(**_kwargs):
        return fake_job

    async def fake_get_job(_job_id: str):
        return None

    import backend.api.routes.codex as codex_routes

    monkeypatch.setattr(codex_routes, "runner", SimpleNamespace(create_job=fake_create_job, get_job=fake_get_job))

    client = TestClient(app)
    resp = client.post("/codex/exec", json={"task": "say hi", "oss": True, "local_provider": "ollama"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "job-123"
    assert body["status"] == "queued"
    assert body["command"] == ["codex", "exec", "--json", "-"]
    assert body["events_tail"] == [{"type": "noop"}]


def test_codex_job_404(monkeypatch) -> None:
    async def fake_get_job(_job_id: str):
        return None

    import backend.api.routes.codex as codex_routes

    monkeypatch.setattr(codex_routes, "runner", SimpleNamespace(get_job=fake_get_job))

    client = TestClient(app)
    resp = client.get("/codex/jobs/does-not-exist")
    assert resp.status_code == 404

