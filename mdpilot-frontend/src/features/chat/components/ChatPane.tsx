import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import { useActiveChatSync } from '../hooks/useActiveChatSync';
import { useAgentChat } from '../hooks/useAgentChat';
import { useChatMessages } from '../hooks/useChatMessages';
import type { ChatId, ChatMessage, MessageId } from '../types';
import { ChatInput } from './ChatInput';
import { MessageList } from './MessageList';

interface Props {
  chatId: ChatId;
}

export function ChatPane({ chatId }: Props) {
  useActiveChatSync(chatId);
  const qc = useQueryClient();

  const messagesQuery = useChatMessages(chatId);
  const agent = useAgentChat(chatId);

  // Agent mode: add user message to cache, then call agent.send with prompt string
  const sendAgent = useCallback(
    (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;
      const id: MessageId = `local-${crypto.randomUUID()}`;
      const userMsg: ChatMessage = {
        id,
        chatId,
        role: 'user',
        content: trimmed,
        createdAt: new Date().toISOString(),
      };
      qc.setQueryData<{ items: ChatMessage[]; nextCursor: string | null }>(
        ['messages', chatId],
        (prev) => ({
        items: [...(prev?.items ?? []), userMsg],
          nextCursor: prev?.nextCursor ?? null,
      }),
      );
      agent.send(trimmed);
    },
    [chatId, qc, agent],
  );

  const messages = messagesQuery.data?.items ?? [];

  const isStreaming = agent.state === 'open';

  return (
    <div className="liquid-glass-panel m-4 flex h-[calc(100%-2rem)] flex-col overflow-hidden rounded-2xl">
      {messagesQuery.isPending ? (
        <div className="flex flex-1 items-center justify-center text-text-2">
          加载消息历史…
        </div>
      ) : (
      <MessageList messages={messages} />
      )}
      <ChatInput
        disabled={messagesQuery.isPending}
        isStreaming={isStreaming}
        onSubmit={sendAgent}
        onStop={agent.stop}
      />
    </div>
  );
}
