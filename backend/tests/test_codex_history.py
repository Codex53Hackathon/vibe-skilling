from __future__ import annotations

import json
from pathlib import Path

from backend.codex.history import read_conversation_messages, read_prompt_history


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_read_prompt_history(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    _write_jsonl(
        codex_home / "history.jsonl",
        [
            {"session_id": "s1", "ts": 10, "text": "hello"},
            {"session_id": "s2", "ts": 20, "text": "world"},
            {"bad": "row"},
        ],
    )

    entries = read_prompt_history(codex_home)
    assert len(entries) == 2
    assert entries[0].session_id == "s1"
    assert entries[1].text == "world"


def test_read_conversation_messages_filters_to_repo(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    repo_root = tmp_path / "repo-a"
    other_repo = tmp_path / "repo-b"
    repo_root.mkdir()
    other_repo.mkdir()

    same_repo_rollout = codex_home / "sessions/2026/02/05/rollout-2026-02-05T00-00-00-abc.jsonl"
    _write_jsonl(
        same_repo_rollout,
        [
            {
                "type": "session_meta",
                "payload": {"id": "session-a", "cwd": str(repo_root.resolve())},
            },
            {
                "timestamp": "2026-02-05T10:00:00.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Question"}],
                },
            },
            {
                "timestamp": "2026-02-05T10:01:00.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "final",
                    "content": [{"type": "output_text", "text": "Answer"}],
                },
            },
        ],
    )

    other_repo_rollout = codex_home / "sessions/2026/02/05/rollout-2026-02-05T00-00-01-def.jsonl"
    _write_jsonl(
        other_repo_rollout,
        [
            {
                "type": "session_meta",
                "payload": {"id": "session-b", "cwd": str(other_repo.resolve())},
            },
            {
                "timestamp": "2026-02-05T11:00:00.000Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Should be filtered"}],
                },
            },
        ],
    )

    messages = read_conversation_messages(codex_home, repo_root=repo_root, include_all_repos=False)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].text == "Question"
    assert messages[1].phase == "final"
    assert messages[1].session_id == "session-a"

    all_messages = read_conversation_messages(codex_home, repo_root=repo_root, include_all_repos=True)
    assert len(all_messages) == 3
