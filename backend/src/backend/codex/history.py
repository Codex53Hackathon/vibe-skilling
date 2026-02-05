from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Literal


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    started_at: datetime | None
    cwd: str | None
    originator: str | None
    rollout_path: Path
    title: str | None


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    session_id: str
    timestamp: datetime | None
    role: Literal["user", "assistant", "developer", "system", "tool"] | str
    text: str
    phase: str | None = None


@dataclass(frozen=True, slots=True)
class PromptHistoryEntry:
    session_id: str
    ts: float
    text: str


def _iter_rollout_files(codex_home: Path) -> Iterable[Path]:
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.exists():
        return []
    return sessions_dir.rglob("rollout-*.jsonl")


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    # timestamps look like "2026-02-05T20:31:08.228Z"
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _flatten_content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n".join(parts).strip()


def _read_jsonl_first_meta(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("type") == "session_meta":
                    payload = obj.get("payload")
                    if isinstance(payload, dict):
                        return payload
                # Some files might have meta later; keep scanning a bit.
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _read_first_user_title(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                if obj.get("type") != "response_item":
                    continue
                payload = obj.get("payload")
                if not isinstance(payload, dict):
                    continue
                if payload.get("type") != "message":
                    continue
                if payload.get("role") != "user":
                    continue
                text = _flatten_content(payload)
                if text:
                    # Trim long prompts.
                    return text.strip().splitlines()[0][:120]
    except (OSError, json.JSONDecodeError):
        return None
    return None


def list_sessions(
    codex_home: Path,
    *,
    repo_root: Path | None = None,
    include_all_repos: bool = False,
    limit: int = 100,
) -> list[SessionSummary]:
    repo_root_resolved = repo_root.resolve() if repo_root else None

    summaries: list[SessionSummary] = []
    for path in _iter_rollout_files(codex_home):
        meta = _read_jsonl_first_meta(path)
        if not meta:
            continue
        session_id = meta.get("id")
        if not isinstance(session_id, str) or not session_id:
            continue
        cwd = meta.get("cwd") if isinstance(meta.get("cwd"), str) else None
        if not include_all_repos and repo_root_resolved and cwd:
            try:
                cwd_path = Path(cwd).resolve()
            except OSError:
                cwd_path = None
            if cwd_path and repo_root_resolved not in (cwd_path, *cwd_path.parents):
                continue

        summaries.append(
            SessionSummary(
                session_id=session_id,
                started_at=_parse_dt(meta.get("timestamp")),
                cwd=cwd,
                originator=meta.get("originator") if isinstance(meta.get("originator"), str) else None,
                rollout_path=path,
                title=_read_first_user_title(path),
            )
        )

    def sort_key(s: SessionSummary) -> tuple[int, float]:
        ts = s.started_at.timestamp() if s.started_at else 0.0
        return (1 if s.started_at else 0, ts)

    summaries.sort(key=sort_key, reverse=True)
    return summaries[:limit]


def find_rollout_by_session_id(codex_home: Path, session_id: str) -> Path | None:
    for path in _iter_rollout_files(codex_home):
        meta = _read_jsonl_first_meta(path)
        if meta and meta.get("id") == session_id:
            return path
    return None


def read_session_messages(
    codex_home: Path,
    session_id: str,
    *,
    include_roles: set[str] | None = None,
) -> list[ConversationMessage]:
    path = find_rollout_by_session_id(codex_home, session_id)
    if not path:
        return []
    include_roles = include_roles or {"user", "assistant", "developer"}

    messages: list[ConversationMessage] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                if obj.get("type") != "response_item":
                    continue
                payload = obj.get("payload")
                if not isinstance(payload, dict):
                    continue
                if payload.get("type") != "message":
                    continue
                role = payload.get("role")
                if not isinstance(role, str) or role not in include_roles:
                    continue
                text = _flatten_content(payload)
                if not text:
                    continue
                messages.append(
                    ConversationMessage(
                        session_id=session_id,
                        timestamp=_parse_dt(obj.get("timestamp")),
                        role=role,
                        text=text,
                        phase=payload.get("phase") if isinstance(payload.get("phase"), str) else None,
                    )
                )
    except (OSError, json.JSONDecodeError):
        return messages

    messages.sort(key=lambda m: m.timestamp.timestamp() if m.timestamp else 0.0)
    return messages


def render_transcript(messages: list[ConversationMessage], *, max_chars: int = 60_000) -> str:
    """
    Render a plain-text transcript suitable for embedding into a prompt.
    """
    chunks: list[str] = []
    remaining = max_chars
    for msg in messages:
        header = f"[{msg.role}]{'[' + msg.phase + ']' if msg.phase else ''}"
        body = msg.text.strip()
        piece = f"{header}\n{body}\n"
        if len(piece) > remaining:
            break
        chunks.append(piece)
        remaining -= len(piece)
    if not chunks:
        return ""
    return "\n".join(chunks).strip()


def read_prompt_history(codex_home: Path, *, limit: int = 500) -> list[PromptHistoryEntry]:
    """
    Best-effort reader for `${CODEX_HOME}/history.jsonl`.
    """
    path = codex_home / "history.jsonl"
    if not path.exists():
        return []
    entries: list[PromptHistoryEntry] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                session_id = obj.get("session_id")
                ts = obj.get("ts")
                text = obj.get("text")
                if not isinstance(session_id, str) or not isinstance(text, str):
                    continue
                try:
                    tsf = float(ts)
                except (TypeError, ValueError):
                    continue
                entries.append(PromptHistoryEntry(session_id=session_id, ts=tsf, text=text))
                if len(entries) >= limit:
                    break
    except (OSError, json.JSONDecodeError):
        return entries
    entries.sort(key=lambda e: e.ts)
    return entries


def read_conversation_messages(
    codex_home: Path,
    *,
    repo_root: Path | None = None,
    include_all_repos: bool = False,
    limit: int = 5_000,
) -> list[ConversationMessage]:
    """
    Aggregate user/assistant messages across sessions.
    Intended for dashboards/debugging (not required for the main UI).
    """
    sessions = list_sessions(
        codex_home,
        repo_root=repo_root,
        include_all_repos=include_all_repos,
        limit=1_000_000,
    )
    out: list[ConversationMessage] = []
    for s in sessions:
        out.extend(read_session_messages(codex_home, s.session_id, include_roles={"user", "assistant"}))
        if len(out) >= limit:
            break
    out.sort(key=lambda m: m.timestamp.timestamp() if m.timestamp else 0.0)
    return out[:limit]
