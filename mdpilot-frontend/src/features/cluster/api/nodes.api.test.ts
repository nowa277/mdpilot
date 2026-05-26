import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import { mockNodes } from './__fixtures__/nodes';
import { listNodes } from './nodes.api';

const server = setupServer(
  http.get('/api/nodes', () => HttpResponse.json(mockNodes)),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('nodes REST API', () => {
  it('fetches all nodes', async () => {
    const nodes = await listNodes();
    expect(nodes).toHaveLength(3);
  });

  it('returns nodes with expected ids', async () => {
    const nodes = await listNodes();
    const ids = nodes.map((n) => n.id);
    expect(ids).toContain('lab02');
    expect(ids).toContain('lab03');
    expect(ids).toContain('lab06');
  });
});
