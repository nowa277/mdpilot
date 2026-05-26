import { Server } from 'mock-socket';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createWsClient } from './client';

const URL = 'ws://localhost:1234/ws/test';
let server: Server;

beforeEach(() => {
  vi.useFakeTimers();
  server = new Server(URL);
});

afterEach(() => {
  server.stop();
  vi.useRealTimers();
});

describe('createWsClient', () => {
  it('connects, dispatches typed events, and sends payloads', async () => {
    const received: Array<{ type: string; payload: unknown }> = [];
    server.on('connection', (socket) => {
      socket.on('message', (raw) => {
        received.push(JSON.parse(String(raw)) as { type: string; payload: unknown });
      });
      socket.send(JSON.stringify({ type: 'pong' }));
    });

    const client = createWsClient(URL);
    const handler = vi.fn();
    client.on('pong', handler);
    await vi.advanceTimersByTimeAsync(20);

    client.send({ type: 'ping' });
    await vi.advanceTimersByTimeAsync(20);

    expect(handler).toHaveBeenCalled();
    expect(received).toEqual([{ type: 'ping' }]);
    client.close();
  });

  it('reconnects with exponential backoff', async () => {
    const client = createWsClient(URL, { initialBackoffMs: 100, maxBackoffMs: 800 });
    await vi.advanceTimersByTimeAsync(20);
    server.close();
    server = new Server(URL);
    const opens: number[] = [];
    server.on('connection', () => opens.push(Date.now()));

    await vi.advanceTimersByTimeAsync(2000);
    expect(opens.length).toBeGreaterThanOrEqual(1);
    client.close();
  });

  it('rejects malformed JSON without crashing', async () => {
    const errors = vi.fn();
    server.on('connection', (socket) => {
      socket.send('not json');
    });
    const client = createWsClient(URL);
    client.on('error', errors);
    await vi.advanceTimersByTimeAsync(50);
    expect(errors).toHaveBeenCalled();
    client.close();
  });
});
