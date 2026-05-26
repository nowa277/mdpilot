import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import { mockNodes } from '../api/__fixtures__/nodes';
import { ClusterMonitorPage } from './ClusterMonitorPage';

const server = setupServer(
  http.get('/api/nodes', () => HttpResponse.json(mockNodes)),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ClusterMonitorPage />
    </QueryClientProvider>,
  );
}

describe('ClusterMonitorPage', () => {
  it('renders 3 node cards from MSW', async () => {
    renderWithProviders();

    expect(await screen.findByText('lab02')).toBeInTheDocument();
    expect(screen.getByText('lab03')).toBeInTheDocument();
    expect(screen.getByText('lab06')).toBeInTheDocument();
  });

  it('shows skeleton/loading text initially', () => {
    renderWithProviders();
    expect(screen.getByText('加载节点状态…')).toBeInTheDocument();
  });

  it('manual refresh button triggers a refetch', async () => {
    const user = userEvent.setup();
    let callCount = 0;

    server.use(
      http.get('/api/nodes', () => {
        callCount++;
        return HttpResponse.json(mockNodes);
      }),
    );

    renderWithProviders();

    // Wait for initial load
    await screen.findByText('lab02');
    const countAfterLoad = callCount;

    const refreshBtn = screen.getByRole('button', { name: '刷新' });
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(callCount).toBeGreaterThan(countAfterLoad);
    });
  });

  it('shows error state when request fails', async () => {
    server.use(
      http.get('/api/nodes', () => HttpResponse.error()),
    );
    renderWithProviders();

    expect(await screen.findByText('无法获取节点状态')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
  });
});
