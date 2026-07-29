// SSE-over-fetch client: EventSource can't POST, so we parse the stream by hand.

export type AgentEventType = "text" | "tool_use" | "done" | "error";

export interface AgentEvent {
  type: AgentEventType;
  text?: string | null;
  tool_name?: string | null;
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
    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame
        .split("\n")
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
