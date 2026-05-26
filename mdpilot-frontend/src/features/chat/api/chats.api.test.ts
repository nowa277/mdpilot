import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import { fetchChats, fetchMessages } from './chats.api';

const server = setupServer(
  http.get('/api/chats', () =>
    HttpResponse.json([
      { id: 'c1', title: 'Test', createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00Z' },
    ]),
  ),
  http.get('/api/chats/c1/messages', () =>
    HttpResponse.json({
      items: [
        { id: 'm1', chatId: 'c1', role: 'user', content: 'hi', createdAt: '2026-01-01T00:00:00Z' },
      ],
      nextCursor: null,
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('chat REST API', () => {
  it('fetches chat list', async () => {
    const chats = await fetchChats();
    expect(chats).toHaveLength(1);
    expect(chats[0]?.id).toBe('c1');
  });

  it('fetches messages for a chat', async () => {
    const result = await fetchMessages('c1');
    expect(result.items).toHaveLength(1);
    expect(result.items[0]?.role).toBe('user');
  });
});
