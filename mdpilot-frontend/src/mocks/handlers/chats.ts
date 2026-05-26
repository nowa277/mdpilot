import type { Chat } from '@shared/types';
import { http, HttpResponse } from 'msw';

import { allChats, allMessages } from '../fixtures';

const chats: Chat[] = [...allChats];

export const chatHandlers = [
  http.get('/api/chats', () => HttpResponse.json(chats)),
  http.post('/api/chats', async ({ request }) => {
    const body = (await request.json()) as { title: string };
    const now = new Date().toISOString();
    const chat: Chat = {
      id: `chat-${crypto.randomUUID()}`,
      title: body.title,
      createdAt: now,
      updatedAt: now,
    };
    chats.unshift(chat);
    return HttpResponse.json(chat, { status: 201 });
  }),
  http.patch('/api/chats/:id', async ({ params, request }) => {
    const body = (await request.json()) as { title?: string };
    const idx = chats.findIndex((c) => c.id === params.id);
    if (idx < 0) return HttpResponse.json({ code: 'NOT_FOUND', detail: 'chat' }, { status: 404 });
    const updated: Chat = { ...chats[idx], ...body, updatedAt: new Date().toISOString() };
    chats[idx] = updated;
    return HttpResponse.json(updated);
  }),
  http.delete('/api/chats/:id', ({ params }) => {
    const idx = chats.findIndex((c) => c.id === params.id);
    if (idx < 0) return HttpResponse.json({ code: 'NOT_FOUND', detail: 'chat' }, { status: 404 });
    chats.splice(idx, 1);
    return new HttpResponse(null, { status: 204 });
  }),
  http.get('/api/chats/:id/messages', ({ params }) => {
    const list = allMessages.filter((m) => m.chatId === params.id);
    return HttpResponse.json({ items: list, nextCursor: null });
  }),
];
