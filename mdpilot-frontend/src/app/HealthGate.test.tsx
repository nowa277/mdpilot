import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import { HealthGate } from './HealthGate';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function wrap(children: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('HealthGate', () => {
  it('renders children when /api/health returns ok', async () => {
    server.use(http.get('/api/health', () => HttpResponse.json({ status: 'ok' })));
    render(wrap(<HealthGate><div>main app</div></HealthGate>));
    await waitFor(() => expect(screen.getByText('main app')).toBeInTheDocument());
  });

  it('shows fallback when /api/health fails', async () => {
    server.use(http.get('/api/health', () => HttpResponse.json({}, { status: 503 })));
    render(wrap(<HealthGate><div>main app</div></HealthGate>));
    await waitFor(
      () =>
        expect(screen.getByRole('heading', { name: /无法连接 lab03 后端/ })).toBeInTheDocument(),
      { timeout: 5000 },
    );
    expect(screen.queryByText('main app')).toBeNull();
  });
});
