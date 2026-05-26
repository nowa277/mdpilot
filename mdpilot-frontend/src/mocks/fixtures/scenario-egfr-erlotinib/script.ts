import type { ChatMessage } from '@shared/types';

import messages from './messages.json' with { type: 'json' };

export interface ScriptStep {
  delayMs: number;
  event:
    | { type: 'message_start'; role: 'assistant'; msgId: string }
    | { type: 'message_chunk'; msgId: string; delta: string }
    | { type: 'message_end'; msgId: string; finishReason: string };
}

const assistant = (messages as ChatMessage[]).find((m) => m.role === 'assistant');

export function buildEgfrScript(): ScriptStep[] {
  if (!assistant) return [];
  const steps: ScriptStep[] = [
    { delayMs: 200, event: { type: 'message_start', role: 'assistant', msgId: assistant.id } },
  ];
  const chunks = assistant.content.match(/.{1,12}/gu) ?? [];
  let delay = 80;
  for (const delta of chunks) {
    steps.push({ delayMs: delay, event: { type: 'message_chunk', msgId: assistant.id, delta } });
    delay = 60;
  }
  steps.push({
    delayMs: 200,
    event: { type: 'message_end', msgId: assistant.id, finishReason: 'stop' },
  });
  return steps;
}
