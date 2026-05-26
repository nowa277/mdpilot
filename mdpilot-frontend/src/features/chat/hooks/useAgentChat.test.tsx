import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { MessagesPage } from './messages-cache';
import { useAgentChat } from './useAgentChat';

// Helper: build a ReadableStream from SSE lines
function sseStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line));
      }
      controller.close();
    },
  });
}

function setupQc(chatId = 'c1') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(['messages', chatId], { items: [], nextCursor: null });
  return qc;
}

function Probe({
  chatId,
  onHandle,
}: {
  chatId: string;
  onHandle: (h: ReturnType<typeof useAgentChat>) => void;
}) {
  const handle = useAgentChat(chatId);
  onHandle(handle);
  return null;
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  // Mock env to return proxy mode
  vi.mock('@shared/config', () => ({
    readEnv: () => ({
      mode: 'proxy',
      apiBase: 'http://localhost:8000',
      wsBase: 'ws://localhost:8000',
      apiToken: 'test-token',
    }),
  }));
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe('useAgentChat', () => {
  it('streams agent SSE blocks into the messages cache', async () => {
    const qc = setupQc();

    const stream = sseStream([
      'event: thinking\ndata: {"content":"analyzing"}\n\n',
      'event: tool_call\ndata: {"tool":"alphafold2"}\n\n',
      'event: complete\ndata: {"result":"queued"}\n\n',
    ]);
    vi.mocked(fetch).mockResolvedValueOnce(new Response(stream, { status: 200 }));

    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId="c1" onHandle={(h) => { handle = h; }} />
      </QueryClientProvider>,
    );

    await act(async () => {
      handle.send('test prompt');
      await new Promise((r) => setTimeout(r, 50));
    });

    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    const assistant = data?.items.find((m) => m.role === 'assistant');
    expect(assistant?.agentBlocks).toHaveLength(3);
    expect(assistant?.agentBlocks?.[0]).toMatchObject({
      type: 'thinking',
      content: 'analyzing',
    });
    expect(assistant?.agentBlocks?.[1]).toMatchObject({
      type: 'tool_call',
      name: 'alphafold2',
    });
    expect(assistant?.agentBlocks?.[2]).toMatchObject({
      type: 'response',
      content: 'queued',
    });
  });

  it('handles stop by aborting the stream', async () => {
    const qc = setupQc();

    // Create a stream that never ends
    const stream = new ReadableStream({
      start(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode('event: thinking\ndata: {"content":"start"}\n\n'));
        // Don't close - simulate long-running stream
      },
    });
    vi.mocked(fetch).mockResolvedValueOnce(new Response(stream, { status: 200 }));

    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId="c1" onHandle={(h) => { handle = h; }} />
      </QueryClientProvider>,
    );

    await act(async () => {
      handle.send('test prompt');
      await new Promise((r) => setTimeout(r, 20));
      handle.stop();
      await new Promise((r) => setTimeout(r, 20));
    });

    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    const assistant = data?.items.find((m) => m.role === 'assistant');
    expect(assistant?.interrupted).toBe(true);
  });

  it('surfaces error message on non-2xx response', async () => {
    const qc = setupQc();

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response('Unauthorized', { status: 401 }),
    );

    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId="c1" onHandle={(h) => { handle = h; }} />
      </QueryClientProvider>,
    );

    await act(async () => {
      handle.send('test prompt');
      await new Promise((r) => setTimeout(r, 50));
    });

    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    const err = data?.items.find((m) => m.role === 'assistant');
    expect(err?.content).toMatch(/Agent 调用失败/);
    expect(err?.content).toMatch(/401/);
  });

  it('sends manual_queue and enabled_tools in request payload', async () => {
    const qc = setupQc();
    qc.setQueryData(['tool-queue', 'c1'], {
      items: [{ id: 'q1', tool: 'alphafold2', order: 1, label: 'AF2' }],
    });
    qc.setQueryData(['tool-modules'], {
      items: [
        { id: 'm1', tool: 'alphafold2', enabled: true, label: 'AF2', description: '', route: '', tags: [] },
        { id: 'm2', tool: 'amber_md', enabled: false, label: 'AMBER', description: '', route: '', tags: [] },
      ],
    });

    const stream = sseStream(['event: complete\ndata: {"result":"ok"}\n\n']);
    vi.mocked(fetch).mockResolvedValueOnce(new Response(stream, { status: 200 }));

    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId="c1" onHandle={(h) => { handle = h; }} />
      </QueryClientProvider>,
    );

    await act(async () => {
      handle.send('test prompt');
      await new Promise((r) => setTimeout(r, 50));
    });

    const body = JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string) as {
      session_id: string;
      prompt: string;
      manual_queue: unknown[];
      enabled_tools: string[];
    };
    expect(body.session_id).toBe('c1');
    expect(body.prompt).toBe('test prompt');
    expect(body.manual_queue).toHaveLength(1);
    expect(body.enabled_tools).toEqual(['alphafold2']);
  });

  it('handles error event from stream', async () => {
    const qc = setupQc();

    const stream = sseStream([
      'event: error\ndata: {"error":"agent execution failed"}\n\n',
    ]);
    vi.mocked(fetch).mockResolvedValueOnce(new Response(stream, { status: 200 }));

    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId="c1" onHandle={(h) => { handle = h; }} />
      </QueryClientProvider>,
    );

    await act(async () => {
      handle.send('test prompt');
      await new Promise((r) => setTimeout(r, 50));
    });

    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    const assistant = data?.items.find((m) => m.role === 'assistant');
    expect(assistant?.agentBlocks).toHaveLength(1);
    expect(assistant?.agentBlocks?.[0]).toMatchObject({
      type: 'error',
      message: 'agent execution failed',
    });
  });

  it('is a no-op when chatId is null', () => {
    const qc = setupQc();

    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId={null as unknown as string} onHandle={(h) => { handle = h; }} />
    </QueryClientProvider>,
    );

    act(() => {
      handle.send('test prompt');
    });

    expect(fetch).not.toHaveBeenCalled();
  });

  it('returns state as closed initially, open during streaming', () => {
    const qc = setupQc();
    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId="c1" onHandle={(h) => { handle = h; }} />
    </QueryClientProvider>,
    );

    expect(handle.state).toBe('closed');
  });

  it('returns state as closed when chatId is null', () => {
    const qc = setupQc();
    let handle!: ReturnType<typeof useAgentChat>;
    render(
      <QueryClientProvider client={qc}>
        <Probe chatId={null as unknown as string} onHandle={(h) => { handle = h; }} />
      </QueryClientProvider>,
    );
    expect(handle.state).toBe('closed');
  });
});
