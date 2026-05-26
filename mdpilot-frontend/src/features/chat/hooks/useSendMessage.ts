import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import type { ChatId, ChatMessage, MessageId } from '../types';

export interface SendMessageDeps {
  chatId: ChatId;
  send: (msg: { type: string; [k: string]: unknown }) => void;
}

export function useSendMessage({ chatId, send }: SendMessageDeps) {
  const qc = useQueryClient();
  const sendMessage = useCallback(
    (content: string, activeSkills?: string[]) => {
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
      const payload: { type: string; content: string; active_skills?: string[] } = {
        type: 'user_message',
        content: trimmed,
      };
      if (activeSkills && activeSkills.length > 0) {
        payload.active_skills = activeSkills;
      }
      send(payload);
    },
    [chatId, qc, send],
  );
  return sendMessage;
}
