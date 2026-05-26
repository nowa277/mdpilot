import type { AgentBlock, ChatMessage } from '@shared/types';
import type { QueryClient } from '@tanstack/react-query';

import type { ChatId, MessageId } from '../types';

export interface MessagesPage {
  items: ChatMessage[];
  nextCursor: string | null;
}

export interface BlockWithId {
  block: AgentBlock;
  toolCallId?: string;
}

export function appendAssistantStart(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    const items = prev?.items ?? [];
    if (items.some((m) => m.id === msgId)) return prev ?? { items, nextCursor: null };
    return {
      items: [
        ...items,
     {
          id: msgId,
          chatId,
          role: 'assistant',
          content: '',
        reasoning: '',
          createdAt: new Date().toISOString(),
        },
      ],
      nextCursor: prev?.nextCursor ?? null,
    };
  });
}

export function appendAssistantChunk(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
  delta: string,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      items: prev.items.map((m) =>
     m.id === msgId ? { ...m, content: m.content + delta } : m,
      ),
    };
  });
}

export function appendAssistantReasoning(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
  delta: string,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      items: prev.items.map((m) =>
        m.id === msgId ? { ...m, reasoning: (m.reasoning ?? '') + delta } : m,
      ),
    };
  });
}

export function appendAssistantError(
  qc: QueryClient,
  chatId: ChatId,
  content: string,
): void {
  const msgId: MessageId = `err-${crypto.randomUUID()}`;
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    const items = prev?.items ?? [];
    return {
      items: [
        ...items,
        {
          id: msgId,
       chatId,
          role: 'assistant',
      content,
          createdAt: new Date().toISOString(),
        },
      ],
      nextCursor: prev?.nextCursor ?? null,
    };
  });
}

export function appendAgentMessageStart(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    const items = prev?.items ?? [];
    if (items.some((m) => m.id === msgId)) return prev ?? { items, nextCursor: null };
    return {
      items: [
        ...items,
        {
          id: msgId,
          chatId,
          role: 'assistant',
          content: '',
          agentBlocks: [],
          createdAt: new Date().toISOString(),
        },
      ],
      nextCursor: prev?.nextCursor ?? null,
    };
  });
}

export function appendAgentBlock(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
  block: AgentBlock,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      items: prev.items.map((m) =>
        m.id === msgId
          ? { ...m, agentBlocks: [...(m.agentBlocks ?? []), block] }
          : m,
      ),
    };
  });
}

export function upsertAgentBlock(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
  blockWithId: BlockWithId,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      items: prev.items.map((m) => {
        if (m.id !== msgId) return m;
        const blocks = [...(m.agentBlocks ?? [])];

        if (blockWithId.toolCallId) {
          // Find existing block and update
        const idx = blocks.findIndex(
	      (b) =>
              b.type === 'tool_call' &&
              (b as any).tool_call_id === blockWithId.toolCallId,
          );
          if (idx >= 0) {
	        blocks[idx] = {
              ...blocks[idx],
              ...blockWithId.block,
              tool_call_id: blockWithId.toolCallId,
	        } as any;
          } else {
            blocks.push({
	      ...blockWithId.block,
              tool_call_id: blockWithId.toolCallId,
            } as any);
          }
        } else if (
          blockWithId.block.type === 'response' ||
          blockWithId.block.type === 'thinking' ||
          blockWithId.block.type === 'streaming'
        ) {
          // Merge into the last block of the same type to keep markdown intact
          const lastBlock = blocks[blocks.length - 1];
          if (lastBlock && lastBlock.type === blockWithId.block.type) {
            const existing = (lastBlock as any).content ?? '';
            const incoming = (blockWithId.block as any).content ?? '';
            blocks[blocks.length - 1] = {
              ...lastBlock,
              content: existing + incoming,
            } as any;
          } else {
            blocks.push(blockWithId.block);
          }
        } else {
          // Other blocks (error, progress, tool_result) — always push
          blocks.push(blockWithId.block);
        }

        return { ...m, agentBlocks: blocks };
      }),
    };
  });
}

export function updateAgentBlock(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
  blockIndex: number,
  updates: Partial<AgentBlock>,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      items: prev.items.map((m) => {
        if (m.id !== msgId) return m;
        const blocks = m.agentBlocks ?? [];
        if (blockIndex < 0 || blockIndex >= blocks.length) return m;
        const updatedBlocks = blocks.map((b, i) => {
          if (i !== blockIndex) return b;
          return { ...b, ...updates } as AgentBlock;
        });
        return {
          ...m,
          agentBlocks: updatedBlocks,
        };
      }),
    };
  });
}

export function markAgentMessageInterrupted(
  qc: QueryClient,
  chatId: ChatId,
  msgId: MessageId,
): void {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      items: prev.items.map((m) =>
        m.id === msgId ? { ...m, interrupted: true } : m,
      ),
    };
  });
}

export function replaceStreamingBlocks(
  qc: QueryClient,
  chatId: string,
  msgId: string,
  newBlock: { type: 'thinking'; content: string } | { type: 'response'; content: string },
) {
  qc.setQueryData<MessagesPage>(['messages', chatId], (prev) => {
    if (!prev) return prev;
    return {
      ...prev,
      items: prev.items.map((m) => {
        if (m.id !== msgId || !m.agentBlocks) return m;
        const filtered = m.agentBlocks.filter((b) => b.type !== 'streaming');
        return { ...m, agentBlocks: [...filtered, newBlock] };
      }),
    };
  });
}
