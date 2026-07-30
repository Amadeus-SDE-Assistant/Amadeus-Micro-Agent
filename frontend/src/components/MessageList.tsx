export interface ChatMessage {
  role: "user" | "assistant" | "system" | "approval";
  text: string;
  /** True while this assistant message is still receiving stream chunks. */
  streaming?: boolean;
  /** approval messages only */
  approvalId?: string;
  decision?: "approved" | "denied";
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
    <div aria-live="polite">
      {messages.map((m, i) =>
        m.role === "approval" ? (
          <div key={i} role="group" aria-label="Approval request">
            <strong>Approval needed</strong>
            <p>{m.text}</p>
            {m.decision ? (
              <p>You {m.decision} this.</p>
            ) : (
              <p>
                <button onClick={() => onDecide(m.approvalId!, "approved")}>
                  Approve
                </button>{" "}
                <button onClick={() => onDecide(m.approvalId!, "denied")}>Deny</button>
              </p>
            )}
          </div>
        ) : (
          <div key={i}>
            <strong>
              {m.role === "user" ? "You" : m.role === "assistant" ? "Amadeus" : "•"}
            </strong>
            <p style={{ whiteSpace: "pre-wrap" }}>{m.text}</p>
          </div>
        ),
      )}
      {busy && <p>Amadeus is thinking…</p>}
    </div>
  );
}
