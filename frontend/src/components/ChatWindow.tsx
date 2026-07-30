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
            { role: "system", text: `Using capability: ${event.tool_name ?? "?"}` },
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
