// SSE-over-fetch client: EventSource can't POST, so we parse the stream by hand.

export interface HistoryMessage {
  role: "user" | "assistant";
  content: { text?: string };
}

/** Chat history for a conversation id (T11.1) — [] for a brand-new id, never a 404. */
export async function fetchHistory(conversationId: string): Promise<HistoryMessage[]> {
  const resp = await fetch(`/api/conversations/${conversationId}/messages`);
  if (!resp.ok) return [];
  const body = (await resp.json()) as { messages: HistoryMessage[] };
  return body.messages;
}

export type AgentEventType =
  | "text"
  | "tool_use"
  | "approval_request"
  | "done"
  | "error";

export interface AgentEvent {
  type: AgentEventType;
  text?: string | null;
  tool_name?: string | null;
  approval_id?: string | null;
  intent?: string | null;
  meta?: Record<string, unknown> | null;
}

export async function* streamChat(
  conversationId: string,
  message: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, message }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    yield { type: "error", text: `Request failed (${resp.status})` };
    return;
  }

  const reader = resp.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += value;
    // SSE frames are separated by a blank line; servers may use \n or \r\n.
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame
        .split(/\r?\n/)
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;
      try {
        yield JSON.parse(dataLine.slice(5).trim()) as AgentEvent;
      } catch {
        // Ignore non-JSON frames (e.g. comments/pings).
      }
    }
  }
}
