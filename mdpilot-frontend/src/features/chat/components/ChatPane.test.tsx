import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { Server } from 'mock-socket';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatPane } from './ChatPane';

// jsdom doesn't implement scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

const WS_URL = 'ws://localhost:1234/ws/chat/c1';
let wsServer: Server;

const server = setupServer(
  http.get('/api/chats/c1/messages', () =>
    HttpResponse.json({ items: [], nextCursor: null }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterAll(() => server.close());

beforeEach(() => {
  vi.stubEnv('VITE_API_MODE', 'mock');
  vi.stubEnv('VITE_WS_BASE', 'ws://localhost:1234');
  vi.stubEnv('VITE_API_BASE', '');
  wsServer = new Server(WS_URL);
});
afterEach(() => {
  server.resetHandlers();
  vi.unstubAllEnvs();
  wsServer.stop();
});

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe('ChatPane', () => {
  it('renders chat interface in Agent mode', async () => {
    render(wrap(<ChatPane chatId="c1" />));
    // Should render the chat input
    expect(await screen.findByRole('textbox')).toBeInTheDocument();
  });

  it('does not render mode toggle buttons', async () => {
    render(wrap(<ChatPane chatId="c1" />));
    // Mode toggle should not exist
    expect(screen.queryByRole('button', { name: '' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Agent' })).not.toBeInTheDocument();
  });
});
