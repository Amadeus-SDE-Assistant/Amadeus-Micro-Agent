export interface ChatMessage {
  role: "user" | "assistant" | "system";
  text: string;
  /** True while this assistant message is still receiving stream chunks. */
  streaming?: boolean;
}

export function MessageList({ messages, busy }: { messages: ChatMessage[]; busy: boolean }) {
  return (
    <div aria-live="polite">
      {messages.map((m, i) => (
        <div key={i}>
          <strong>{m.role === "user" ? "You" : m.role === "assistant" ? "Amadeus" : "•"}</strong>
          <p style={{ whiteSpace: "pre-wrap" }}>{m.text}</p>
        </div>
      ))}
      {busy && <p>Amadeus is thinking…</p>}
    </div>
  );
}
