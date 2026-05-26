export interface AgentSseFrame {
  event: string;
  data: Record<string, unknown>;
}

export interface ParseResult {
  events: AgentSseFrame[];
  buffer: string;
}

/**
 * Parse named SSE frames from agent stream.
 * Format: event: <name>\ndata: <json>\n\n
 * Returns parsed events and any incomplete buffer.
 */
export function parseAgentSseFrames(
  previousBuffer: string,
  chunk: string,
): ParseResult {
  const combined = previousBuffer + chunk;
  const events: AgentSseFrame[] = [];

  // Split by double newline to get complete frames
  const parts = combined.split('\n\n');

  // Last part might be incomplete, keep as buffer
  let buffer = parts.pop() ?? '';
  // Trim buffer if it's only whitespace
  if (buffer.trim() === '') buffer = '';

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;

    const lines = trimmed.split('\n');
    let eventName: string | null = null;
    let dataLine: string | null = null;

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLine = line.slice(5).trim();
      }
    }

    // Skip if missing event or data
    if (!eventName || !dataLine) continue;

    // Parse JSON data
    try {
   const data = JSON.parse(dataLine) as Record<string, unknown>;
      events.push({ event: eventName, data });
    } catch {
      // Skip malformed JSON
      continue;
    }
  }

  return { events, buffer };
}
