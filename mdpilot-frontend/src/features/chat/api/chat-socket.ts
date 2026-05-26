import { wsUrl } from '@shared/api';
import { createWsClient, type WsClient } from '@shared/ws';

import type { ChatId } from '../types';

export function chatSocketUrl(chatId: ChatId): string {
  return wsUrl(`/ws/chat/${encodeURIComponent(chatId)}`);
}

export function openChatSocket(chatId: ChatId): WsClient {
  return createWsClient(chatSocketUrl(chatId));
}
