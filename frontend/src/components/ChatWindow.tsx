import { useRef, useState } from "react";
import { streamChat } from "../lib/sse";
import { type ChatMessage, MessageList } from "./MessageList";

export function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const conversationId = useRef(crypto.randomUUID().slice(0, 8));

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", text }]);

    let assistantIndex = -1;
    try {
      for await (const event of streamChat(conversationId.current, text)) {
        if (event.type === "text" && event.text) {
          const chunk = event.text;
          setMessages((prev) => {
            const next = [...prev];
            if (assistantIndex === -1) {
              assistantIndex = next.length;
              next.push({ role: "assistant", text: chunk });
            } else {
              next[assistantIndex] = {
                ...next[assistantIndex],
                text: next[assistantIndex].text + chunk,
              };
            }
            return next;
          });
        } else if (event.type === "tool_use") {
          setMessages((prev) => [
            ...prev,
            { role: "system", text: `Using capability: ${event.tool_name ?? "?"}` },
          ]);
          assistantIndex = -1;
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
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Amadeus</h1>
      <MessageList messages={messages} busy={busy} />
      <form
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
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </main>
  );
}
