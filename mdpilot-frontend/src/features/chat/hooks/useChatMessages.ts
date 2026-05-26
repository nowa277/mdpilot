import { useQuery } from '@tanstack/react-query';

import { fetchMessages } from '../api/chats.api';
import type { ChatId } from '../types';

export function useChatMessages(chatId: ChatId | null) {
  return useQuery({
    queryKey: ['messages', chatId],
    queryFn: () => fetchMessages(chatId as ChatId),
    enabled: chatId !== null,
    staleTime: Number.POSITIVE_INFINITY,
  });
}
