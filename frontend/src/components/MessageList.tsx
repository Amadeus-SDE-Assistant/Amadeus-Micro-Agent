export interface ChatMessage {
  role: "user" | "assistant" | "system" | "approval";
  text: string;
  /** True while this assistant message is still receiving stream chunks. */
  streaming?: boolean;
  /** approval messages only */
  approvalId?: string;
  decision?: "approved" | "denied";
}

/** Presentational mapping from internal tool ids to the product's own language. */
const CAPABILITY_NAMES: Record<string, string> = {
  mcp__jobseeker__resume_store: "Resume storage",
  mcp__jobseeker__strategy_convo: "Career strategy",
  mcp__jobseeker__application_track: "Application tracking",
  mcp__jobseeker__job_search_match: "Job search & match",
  mcp__jobseeker__emotional_support: "Support",
  ToolSearch: "Preparing tools",
};

export function friendlyCapability(raw: string): string {
  return CAPABILITY_NAMES[raw] ?? raw;
}

/** Minimal presentational markdown: only **bold** — agent replies use it heavily. */
function renderInline(text: string) {
  const parts = text.split(/\*\*([^*]+)\*\*/g);
  return parts.map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part));
}

export function MessageList({
  messages,
  busy,
  onDecide,
}: {
  messages: ChatMessage[];
  busy: boolean;
  onDecide: (approvalId: string, decision: "approved" | "denied") => void;
}) {
  return (
    <div className="thread" aria-live="polite">
      {messages.length === 0 && !busy && (
        <div className="msg assistant">
          <span className="author">Amadeus</span>
          <p>
            Good to see you. Ask me anything about your search — strategy, applications,
            openings, or just how it's going. Upload your resume below and I'll keep
            your experience on file.
          </p>
        </div>
      )}
      {messages.map((m, i) =>
        m.role === "approval" ? (
          <div key={i} className="approval" role="group" aria-label="Approval request">
            <strong className="author">Amadeus asks permission</strong>
            <p>{m.text}</p>
            {m.decision ? (
              <p className="decided">
                {m.decision === "approved" ? "You approved this." : "You declined this."}
              </p>
            ) : (
              <p className="actions">
                <button
                  className="btn-primary"
                  onClick={() => onDecide(m.approvalId!, "approved")}
                >
                  Approve
                </button>
                <button
                  className="btn-quiet"
                  onClick={() => onDecide(m.approvalId!, "denied")}
                >
                  Deny
                </button>
              </p>
            )}
          </div>
        ) : (
          <div
            key={i}
            className={
              m.role === "user" ? "msg user" : m.role === "assistant" ? "msg assistant" : "note"
            }
          >
            {m.role !== "system" && (
              <span className="author">{m.role === "user" ? "You" : "Amadeus"}</span>
            )}
            <p>{m.role === "assistant" ? renderInline(m.text) : m.text}</p>
          </div>
        ),
      )}
      {busy && <p className="thinking">Amadeus is thinking</p>}
    </div>
  );
}
