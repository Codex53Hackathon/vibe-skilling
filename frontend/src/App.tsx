import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

type SessionSummary = {
  id: string;
  title: string | null;
  started_at: string | null;
  cwd: string | null;
  originator: string | null;
};

type ConversationMessage = {
  role: string;
  text: string;
  timestamp: string | null;
  phase: string | null;
};

function formatTimestamp(raw: string): string {
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return raw;
  }
  return date.toLocaleString();
}

async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const resp = await fetch(path, { signal });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}${text ? `: ${text}` : ""}`);
  }
  return (await resp.json()) as T;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}${text ? `: ${text}` : ""}`);
  }
  return (await resp.json()) as T;
}

type Job = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "canceled";
  returncode: number | null;
  stderr_tail: string[];
  last_message: string | null;
};

type InsightsRunResp = { job_id: string; artifact_id: string };
type ProposalRunResp = { job_id: string; proposal_id: string };

type InsightsArtifact = {
  artifact_id: string;
  session_id: string;
  markdown: string | null;
  json: unknown | null;
};

type ProposalResp = {
  proposal_id: string;
  session_id: string;
  status: "missing" | "ready";
  diff: string | null;
  summary: string | null;
  files_touched: string[];
  validation_errors: string[];
};

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);

  const [mode, setMode] = useState<"fork" | "resume">("fork");

  const [insightsPrompt, setInsightsPrompt] = useState(
    "Extract actionable insights for improving repo-scoped Codex skills and AGENTS.md. Include concrete suggestions and gaps.",
  );
  const [insightsJobId, setInsightsJobId] = useState<string | null>(null);
  const [insightsArtifactId, setInsightsArtifactId] = useState<string | null>(null);
  const [insights, setInsights] = useState<InsightsArtifact | null>(null);

  const [proposalPrompt, setProposalPrompt] = useState<string>("");
  const [proposalJobId, setProposalJobId] = useState<string | null>(null);
  const [proposalId, setProposalId] = useState<string | null>(null);
  const [proposal, setProposal] = useState<ProposalResp | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSessions() {
      try {
        setSessionsLoading(true);
        setSessionsError(null);
        const data = await apiGet<SessionSummary[]>("/codex/sessions?limit=100", controller.signal);
        setSessions(data);
        setSelectedSessionId((prev) => prev ?? data[0]?.id ?? null);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        setSessionsError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setSessionsLoading(false);
      }
    }

    void loadSessions();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedSessionId) return;
    const controller = new AbortController();

    async function loadMessages() {
      try {
        setMessagesLoading(true);
        setMessagesError(null);
        const data = await apiGet<{ id: string; messages: ConversationMessage[] }>(
          `/codex/sessions/${encodeURIComponent(selectedSessionId)}`,
          controller.signal,
        );
        setMessages(data.messages);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        setMessagesError(err instanceof Error ? err.message : "Unknown error");
        setMessages([]);
      } finally {
        setMessagesLoading(false);
      }
    }

    void loadMessages();
    return () => controller.abort();
  }, [selectedSessionId]);

  useEffect(() => {
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current);
    };
  }, []);

  async function pollJob(jobId: string, onDone: (job: Job) => void) {
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = window.setInterval(async () => {
      try {
        const job = await apiGet<Job>(`/codex/jobs/${encodeURIComponent(jobId)}?tail=50`);
        if (job.status !== "queued" && job.status !== "running") {
          if (pollTimer.current) window.clearInterval(pollTimer.current);
          pollTimer.current = null;
          onDone(job);
        }
      } catch {
        // ignore transient polling errors
      }
    }, 800);
  }

  async function runInsights() {
    if (!selectedSessionId) return;
    setActionError(null);
    setInsights(null);
    setProposal(null);
    setProposalId(null);
    setProposalJobId(null);
    try {
      const resp = await apiPost<InsightsRunResp>("/codex/insights/run", {
        session_id: selectedSessionId,
        prompt: insightsPrompt,
        mode,
        workdir: ".",
      });
      setInsightsJobId(resp.job_id);
      setInsightsArtifactId(resp.artifact_id);
      await pollJob(resp.job_id, async (job) => {
        if (job.status !== "succeeded") {
          setActionError(job.stderr_tail?.slice(-1)[0] ?? "Insights job failed");
          return;
        }
        const artifact = await apiGet<InsightsArtifact>(
          `/codex/insights/artifacts/${encodeURIComponent(selectedSessionId)}/${encodeURIComponent(
            resp.artifact_id,
          )}`,
        );
        setInsights(artifact);
      });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to run insights");
    }
  }

  async function runProposal() {
    if (!selectedSessionId || !insightsArtifactId) return;
    setActionError(null);
    setProposal(null);
    try {
      const resp = await apiPost<ProposalRunResp>("/codex/proposals/run", {
        session_id: selectedSessionId,
        insight_artifact_id: insightsArtifactId,
        prompt: proposalPrompt || null,
        mode,
        workdir: ".",
      });
      setProposalJobId(resp.job_id);
      setProposalId(resp.proposal_id);
      await pollJob(resp.job_id, async (job) => {
        if (job.status !== "succeeded") {
          setActionError(job.stderr_tail?.slice(-1)[0] ?? "Proposal job failed");
          return;
        }
        const p = await apiGet<ProposalResp>(`/codex/proposals/${encodeURIComponent(resp.proposal_id)}`);
        setProposal(p);
      });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to run proposal");
    }
  }

  async function applyProposal() {
    if (!proposalId) return;
    setActionError(null);
    try {
      const resp = await apiPost<{ applied: boolean; errors: string[] }>(
        `/codex/proposals/${encodeURIComponent(proposalId)}/apply`,
        { confirm: true },
      );
      if (!resp.applied) {
        setActionError(resp.errors?.[0] ?? "Apply failed");
      } else {
        const refreshed = await apiGet<ProposalResp>(`/codex/proposals/${encodeURIComponent(proposalId)}`);
        setProposal(refreshed);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to apply proposal");
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Codex Orchestrator</h1>
        <div className="mode">
          <label>
            Mode
            <select value={mode} onChange={(e) => setMode(e.target.value as "fork" | "resume")}>
              <option value="fork">Fork (detached)</option>
              <option value="resume">Resume</option>
            </select>
          </label>
        </div>
      </header>

      <div className="grid">
        <aside className="pane sessions">
          <div className="paneHeader">
            <h2>Sessions</h2>
            <div className="small">{sessions.length}</div>
          </div>
          {sessionsLoading ? <div className="status">Loading…</div> : null}
          {sessionsError ? <div className="status error">{sessionsError}</div> : null}
          <div className="sessionList">
            {sessions.map((s) => (
              <button
                key={s.id}
                className={`sessionRow ${s.id === selectedSessionId ? "active" : ""}`}
                type="button"
                onClick={() => setSelectedSessionId(s.id)}
              >
                <div className="sessionTitle">{s.title ?? s.id}</div>
                <div className="sessionMeta">
                  {s.started_at ? formatTimestamp(s.started_at) : "—"}
                </div>
              </button>
            ))}
          </div>
        </aside>

        <main className="pane transcript">
          <div className="paneHeader">
            <h2>Transcript</h2>
            {selectedSessionId ? <div className="small">{selectedSessionId}</div> : null}
          </div>
          {messagesLoading ? <div className="status">Loading…</div> : null}
          {messagesError ? <div className="status error">{messagesError}</div> : null}
          <div className="messageList" aria-live="polite">
            {messages.map((m, idx) => (
              <article key={`${idx}-${m.timestamp ?? ""}-${m.role}`} className={`message ${m.role}`}>
                <div className="meta">
                  <span className="role">{m.role}</span>
                  {m.timestamp ? <time dateTime={m.timestamp}>{formatTimestamp(m.timestamp)}</time> : null}
                </div>
                <pre>{m.text}</pre>
              </article>
            ))}
          </div>
        </main>

        <aside className="pane actions">
          <div className="paneHeader">
            <h2>Actions</h2>
          </div>
          {actionError ? <div className="status error">{actionError}</div> : null}

          <section className="card">
            <h3>Insights</h3>
            <textarea
              value={insightsPrompt}
              onChange={(e) => setInsightsPrompt(e.target.value)}
              rows={6}
              placeholder="Prompt…"
            />
            <div className="row">
              <button type="button" onClick={() => void runInsights()} disabled={!selectedSessionId}>
                Run
              </button>
              <div className="small">
                {insightsJobId ? `job: ${insightsJobId}` : null}
              </div>
            </div>
            {insights?.markdown ? <pre className="output">{insights.markdown}</pre> : null}
          </section>

          <section className="card">
            <h3>Proposal (diff)</h3>
            <textarea
              value={proposalPrompt}
              onChange={(e) => setProposalPrompt(e.target.value)}
              rows={4}
              placeholder="Optional extra constraints…"
            />
            <div className="row">
              <button
                type="button"
                onClick={() => void runProposal()}
                disabled={!selectedSessionId || !insightsArtifactId}
              >
                Generate
              </button>
              <div className="small">{proposalJobId ? `job: ${proposalJobId}` : null}</div>
            </div>
            {proposal?.validation_errors?.length ? (
              <div className="status error">
                {proposal.validation_errors.join("\n")}
              </div>
            ) : null}
            {proposal?.diff ? <pre className="output">{proposal.diff}</pre> : null}
            <div className="row">
              <button
                type="button"
                onClick={() => void applyProposal()}
                disabled={!proposalId || !proposal?.diff || (proposal.validation_errors?.length ?? 0) > 0}
              >
                Approve & apply
              </button>
              <div className="small">{proposalId ? `proposal: ${proposalId}` : null}</div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
