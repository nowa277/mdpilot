import { api } from '@shared/api';
import type { Chat, ChatId, ChatMessage, SkillInfo } from '@shared/types';

export async function fetchChats(): Promise<Chat[]> {
  const resp = await api().get<Chat[]>('/api/chats');
  return resp.data;
}

export interface MessagePage {
  items: ChatMessage[];
  nextCursor: string | null;
}

export async function fetchMessages(chatId: ChatId, cursor?: string): Promise<MessagePage> {
  const resp = await api().get<MessagePage>(`/api/chats/${encodeURIComponent(chatId)}/messages`, {
    params: cursor ? { cursor } : undefined,
  });
  return resp.data;
}

export interface CreateChatInput {
  title: string;
}

export async function createChat(input: CreateChatInput): Promise<Chat> {
  const resp = await api().post<Chat>('/api/chats', input);
  return resp.data;
}

export async function updateChat(id: ChatId, patch: { title: string }): Promise<Chat> {
  const resp = await api().patch<Chat>(`/api/chats/${encodeURIComponent(id)}`, patch);
  return resp.data;
}

export async function deleteChat(id: ChatId): Promise<void> {
  await api().delete(`/api/chats/${encodeURIComponent(id)}`);
}

export async function fetchSkills(): Promise<SkillInfo[]> {
  const resp = await api().get<SkillInfo[]>('/api/v1/skills');
  return resp.data;
}
