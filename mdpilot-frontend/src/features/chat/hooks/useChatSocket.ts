import { useReconnectingWS } from '@shared/hooks';
import type { WsMessage } from '@shared/ws';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { chatSocketUrl } from '../api/chat-socket';
import type { ChatId } from '../types';
import {
  appendAssistantChunk,
  appendAssistantStart,
} from './messages-cache';

export interface ChatSocketHandle {
  send: (msg: WsMessage) => void;
  state: ReturnType<typeof useReconnectingWS>['state'];
}

export function useChatSocket(chatId: ChatId | null): ChatSocketHandle {
  const url = chatId ? chatSocketUrl(chatId) : null;
  const ws = useReconnectingWS(url);
  const qc = useQueryClient();

  useEffect(() => {
    if (!chatId || !ws.client) return;
    const c = ws.client;

    const onStart = (msg: WsMessage) => {
      const ev = msg as WsMessage & { msgId: string };
      appendAssistantStart(qc, chatId, ev.msgId);
    };

    const onChunk = (msg: WsMessage) => {
      const ev = msg as WsMessage & { msgId: string; delta: string };
      appendAssistantChunk(qc, chatId, ev.msgId, ev.delta);
    };

    const onEnd = () => {
      // Phase 1B: no-op. P2 will handle finishReason.
    };
    const onTaskCreated = () => {
      void qc.invalidateQueries({ queryKey: ['tasks'] });
    };
    const onTaskStatus = () => {
      void qc.invalidateQueries({ queryKey: ['tasks'] });
    };

    const offs = [
      c.on('message_start', onStart),
      c.on('message_chunk', onChunk),
      c.on('message_end', onEnd),
      c.on('task_created', onTaskCreated),
    c.on('task_status_changed', onTaskStatus),
    ];
    return () => {
      for (const off of offs) off();
    };
  }, [chatId, qc, ws.client]);

  return { send: (msg: WsMessage) => ws.send(msg), state: ws.state };
}
