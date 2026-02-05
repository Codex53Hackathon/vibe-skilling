#!/usr/bin/env bun

// Reads messages from a running Codex CLI session in real-time.
// Auto-detects new sessions and switches to them.
//
// Usage:
//   bun codex-reader.js          # follow latest session, auto-switch on new ones
//   bun codex-reader.js <path>   # pin to a specific session file (no auto-switch)

import { watch, existsSync, mkdirSync, openSync, readSync, fstatSync, closeSync } from "fs";
import { homedir } from "os";
import { execSync, execFileSync } from "child_process";

const sessionsDir = `${homedir()}/.codex/sessions`;
const pinned = process.argv[2];
const POLL_MS = 200;
const INGEST_URL = "https://vibe-skilling-api.onrender.com/conversation/ingest";

let currentFile = null;
let fd = -1;
let offset = 0;
let partial = ""; // leftover bytes that don't end with \n yet
let fileWatcher = null;
let pollTimer = null;

function notify(title, subtitle, message) {
  try {
    execFileSync("terminal-notifier", [
      "-title", title,
      "-subtitle", subtitle,
      "-message", message,
      "-sound", "default",
    ]);
  } catch (err) {
    console.error(`\x1b[31m    [notify error] ${err.message}\x1b[0m`);
  }
}

function getSessionId() {
  if (!currentFile) return "unknown-session";
  return currentFile.split("/").pop().replace(/\.jsonl$/, "");
}

async function sendToIngest(speaker, message) {
  const body = {
    session_id: getSessionId(),
    events: [{ speaker, message }],
  };
  try {
    const res = await fetch(INGEST_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      notify("Ingest Failed", `${res.status} ${res.statusText}`, "POST /conversation/ingest returned non-OK");
      return;
    }
    const data = await res.json();
    console.log(`\x1b[90m    [ingest] ← ${JSON.stringify(data)}\x1b[0m`);
    if (data.status === "suggested_existing_skill") {
      console.log(`\x1b[33m    [skill suggestion] Update '${data.skill.name}' → ${data.skill.path}\x1b[0m`);
      notify("Skill Suggestion", data.skill.name, data.message);
    } else if (data.status === "suggested_new_skill") {
      console.log(`\x1b[32m    [new skill] Create '${data.skill.name}' → ${data.skill.path}\x1b[0m`);
      notify("New Skill", data.skill.name, data.message);
    }
  } catch (err) {
    notify("Ingest Error", "Connection failed", err.message);
  }
}

function getLatestSession() {
  try {
    return execSync(`fd -t f . ${sessionsDir} | sort | tail -1`)
      .toString()
      .trim();
  } catch {
    return null;
  }
}

function todayDir() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${sessionsDir}/${y}/${m}/${day}`;
}

// Read any new bytes appended since last read using the open fd
function drain() {
  if (fd < 0) return;

  const stat = fstatSync(fd);
  const size = stat.size;
  if (size <= offset) return;

  const buf = Buffer.alloc(size - offset);
  const bytesRead = readSync(fd, buf, 0, buf.length, offset);
  if (bytesRead === 0) return;
  offset += bytesRead;

  const chunk = partial + buf.toString("utf-8", 0, bytesRead);
  const lines = chunk.split("\n");

  // Last element is either "" (line ended with \n) or a partial line
  partial = lines.pop();

  for (const line of lines) {
    if (!line.trim()) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    handleMessage(msg);
  }
}

function handleMessage(msg) {
  const { type, payload } = msg;

  if (type === "event_msg" && payload?.type === "user_message") {
    console.log(`\x1b[36m>>> USER:\x1b[0m ${payload.message}`);
    console.log(`\x1b[90m    [ingest] → user: ${truncate(payload.message, 120)}\x1b[0m`);
    sendToIngest("user", payload.message);
    return;
  }

  if (type === "event_msg" && payload?.type === "agent_message") {
    console.log(`\x1b[33m<<< MODEL:\x1b[0m ${payload.message}`);
    console.log(`\x1b[90m    [ingest] → assistant: ${truncate(payload.message, 120)}\x1b[0m`);
    sendToIngest("assistant", payload.message);
    return;
  }

  if (
    type === "response_item" &&
    payload?.role === "assistant" &&
    payload?.phase === "commentary"
  ) {
    const text = payload.content?.map((c) => c.text).join("") ?? "";
    if (text) console.log(`\x1b[90m    [thinking] ${text}\x1b[0m`);
    return;
  }

  if (type === "event_msg" && payload?.type === "tool_call") {
    console.log(
      `\x1b[35m    [tool] ${payload.name}\x1b[0m${payload.args ? ` ${truncate(payload.args, 120)}` : ""}`
    );
    return;
  }

  if (type === "event_msg" && payload?.type === "token_count" && payload?.info) {
    const u = payload.info.last_token_usage;
    if (u) {
      console.log(
        `\x1b[90m    [tokens] in:${u.input_tokens} cached:${u.cached_input_tokens} out:${u.output_tokens} reasoning:${u.reasoning_output_tokens}\x1b[0m`
      );
    }
    return;
  }
}

function truncate(s, n) {
  return s.length > n ? s.slice(0, n) + "..." : s;
}

function attachToFile(file) {
  if (file === currentFile) return;

  // Clean up previous
  if (fileWatcher) fileWatcher.close();
  if (pollTimer) clearInterval(pollTimer);
  if (fd >= 0) closeSync(fd);

  currentFile = file;
  offset = 0;
  partial = "";

  console.log(`\n\x1b[32m--- new session: ${file.split("/").pop()} ---\x1b[0m\n`);

  // Open fd in read-only mode and keep it open
  fd = openSync(currentFile, "r");

  // Initial drain
  drain();

  // fs.watch for immediate notification when the file changes
  fileWatcher = watch(currentFile, () => drain());

  // Poll as backup - fs.watch can miss events or batch them
  pollTimer = setInterval(drain, POLL_MS);
}

// --- main ---

if (pinned) {
  attachToFile(pinned);
} else {
  const latest = getLatestSession();
  if (latest) attachToFile(latest);

  // Poll for new session files
  setInterval(() => {
    const newest = getLatestSession();
    if (newest && newest !== currentFile) {
      attachToFile(newest);
    }
  }, 1000);

  // Watch today's dir for faster new-session detection
  const dir = todayDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  watch(dir, (event, filename) => {
    if (!filename) return;
    const full = `${dir}/${filename}`;
    if (full !== currentFile && existsSync(full)) {
      attachToFile(full);
    }
  });
}

console.log(
  `\x1b[90mListening for Codex sessions... (ctrl+c to stop)\x1b[0m`
);
