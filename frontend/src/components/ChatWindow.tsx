import { useEffect, useRef, useState } from "react";
import { fetchHistory, streamChat } from "../lib/sse";
import { type ChatMessage, MessageList, friendlyCapability } from "./MessageList";

const CONVERSATION_ID_KEY = "amadeus:conversationId";

/** Same id across reloads (T11.1) so history rehydration has something to key on. */
function getOrCreateConversationId(): string {
  const stored = localStorage.getItem(CONVERSATION_ID_KEY);
  if (stored) return stored;
  const fresh = crypto.randomUUID().slice(0, 8);
  localStorage.setItem(CONVERSATION_ID_KEY, fresh);
  return fresh;
}

export function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const conversationId = useRef(getOrCreateConversationId());

  useEffect(() => {
    let cancelled = false;
    fetchHistory(conversationId.current).then((history) => {
      if (cancelled || history.length === 0) return;
      // Don't clobber a message the user already sent while this was in flight.
      setMessages((prev) =>
        prev.length > 0
          ? prev
          : history.map((m) => ({ role: m.role, text: m.content.text ?? "" })),
      );
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", text }]);

    try {
      for await (const event of streamChat(conversationId.current, text)) {
        if (event.type === "text" && event.text) {
          const chunk = event.text;
          // Pure updater (StrictMode double-invokes it): append to a
          // still-streaming assistant tail, otherwise start a new message.
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant" && last.streaming) {
              return [
                ...prev.slice(0, -1),
                { ...last, text: last.text + chunk },
              ];
            }
            return [...prev, { role: "assistant", text: chunk, streaming: true }];
          });
        } else if (event.type === "tool_use") {
          setMessages((prev) => [
            ...prev,
            { role: "system", text: `· ${friendlyCapability(event.tool_name ?? "?")}` },
          ]);
        } else if (event.type === "approval_request") {
          setMessages((prev) => [
            ...prev,
            {
              role: "approval",
              text: event.intent ?? "The agent wants to perform a write action.",
              approvalId: event.approval_id ?? "",
            },
          ]);
        } else if (event.type === "error") {
          setMessages((prev) => [
            ...prev,
            { role: "system", text: `Error: ${event.text ?? "unknown error"}` },
          ]);
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "system", text: "Error: connection to the server was lost." },
      ]);
    } finally {
      setMessages((prev) =>
        prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
      );
      setBusy(false);
    }
  }

  async function decide(approvalId: string, decision: "approved" | "denied") {
    // Mark locally first so the buttons can't double-fire.
    setMessages((prev) =>
      prev.map((m) =>
        m.role === "approval" && m.approvalId === approvalId && !m.decision
          ? { ...m, decision }
          : m,
      ),
    );
    try {
      await fetch(`/api/approvals/${approvalId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "system", text: "Error: could not deliver your decision." },
      ]);
    }
  }

  return (
    <main>
      <MessageList messages={messages} busy={busy} onDecide={(id, d) => void decide(id, d)} />
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your job search…"
          aria-label="Message"
          disabled={busy}
        />
        <button type="submit" className="btn-primary" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </main>
  );
}
