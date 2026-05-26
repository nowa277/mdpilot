import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createChat,
  type CreateChatInput,
  deleteChat,
  fetchChats,
  updateChat,
} from '../api/chats.api';
import type { Chat, ChatId } from '../types';

export function useChatList() {
  return useQuery({
    queryKey: ['chats'],
    queryFn: fetchChats,
    staleTime: 30_000,
  });
}

export function useCreateChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateChatInput) => createChat(input),
    onSuccess: (chat) => {
      qc.setQueryData<Chat[]>(['chats'], (prev) => [chat, ...(prev ?? [])]);
    },
  });
}

export function useUpdateChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: ChatId; title: string }) => updateChat(id, { title }),
    onSuccess: (chat) => {
      qc.setQueryData<Chat[]>(['chats'], (prev) =>
        (prev ?? []).map((c) => (c.id === chat.id ? chat : c)),
      );
    },
  });
}

export function useDeleteChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: ChatId) => deleteChat(id),
    onSuccess: (_data, id) => {
      qc.setQueryData<Chat[]>(['chats'], (prev) => (prev ?? []).filter((c) => c.id !== id));
    },
  });
}
