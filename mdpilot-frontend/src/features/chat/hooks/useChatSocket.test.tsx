import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render } from '@testing-library/react';
import { Server } from 'mock-socket';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useChatSocket } from './useChatSocket';

function setupQueryClient(initialMessages: { items: unknown[]; nextCursor: null }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(['messages', 'c1'], initialMessages);
  return qc;
}

function Probe({ chatId }: { chatId: string }) {
  useChatSocket(chatId);
  return null;
}

const URL = 'ws://localhost:1234/ws/chat/c1';
let server: Server;

beforeEach(() => {
  vi.stubEnv('VITE_API_MODE', 'mock');
  vi.stubEnv('VITE_WS_BASE', 'ws://localhost:1234');
  vi.stubEnv('VITE_API_BASE', '');
  server = new Server(URL);
});
afterEach(() => {
  vi.unstubAllEnvs();
  server.stop();
});

describe('useChatSocket', () => {
  it('appends streamed assistant content to query cache', async () => {
    server.on('connection', (socket) => {
      socket.send(
      JSON.stringify({ type: 'message_start', role: 'assistant', msgId: 'a1' }),
      );
      socket.send(JSON.stringify({ type: 'message_chunk', msgId: 'a1', delta: 'Hello ' }));
      socket.send(JSON.stringify({ type: 'message_chunk', msgId: 'a1', delta: 'world' }));
      socket.send(JSON.stringify({ type: 'message_end', msgId: 'a1', finishReason: 'stop' }));
    });

    const qc = setupQueryClient({ items: [], nextCursor: null });
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId="c1" />
      </QueryClientProvider>,
    );

    await act(async () => {
      await new Promise((r) => setTimeout(r, 80));
    });

    const data = qc.getQueryData<{ items: Array<{ id: string; content: string }> }>([
      'messages',
      'c1',
    ]);
    expect(data?.items.find((m) => m.id === 'a1')?.content).toBe('Hello world');
  });
});
