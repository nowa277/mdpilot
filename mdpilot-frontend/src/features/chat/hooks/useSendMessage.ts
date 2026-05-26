import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import type { ChatId, ChatMessage, MessageId } from '../types';

export interface SendMessageDeps {
  chatId: ChatId;
  send: (msg: { type: string; [k: string]: unknown }) => void;
}

export function useSendMessage({ chatId, send }: SendMessageDeps) {
  const qc = useQueryClient();
  return useCallback(
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
      send({ type: 'user_message', content: trimmed });
    },
    [chatId, qc, send],
  );
}
