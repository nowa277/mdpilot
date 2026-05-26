import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it } from 'vitest';

import {
  appendAgentBlock,
  appendAgentMessageStart,
  appendAssistantChunk,
  appendAssistantError,
  appendAssistantReasoning,
  appendAssistantStart,
  markAgentMessageInterrupted,
  type MessagesPage,
  updateAgentBlock,
  upsertAgentBlock,
} from './messages-cache';

function makeQc(initial?: MessagesPage) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (initial) qc.setQueryData(['messages', 'c1'], initial);
  return qc;
}

describe('messages-cache helpers', () => {
  it('appendAssistantStart adds a blank assistant message', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAssistantStart(qc, 'c1', 'msg1');
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items).toHaveLength(1);
    expect(data?.items[0]).toMatchObject({ id: 'msg1', role: 'assistant', content: '' });
  });

  it('appendAssistantStart is idempotent for duplicate msgId', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAssistantStart(qc, 'c1', 'msg1');
    appendAssistantStart(qc, 'c1', 'msg1');
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items).toHaveLength(1);
  });

  it('appendAssistantChunk appends delta to existing message', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAssistantStart(qc, 'c1', 'msg1');
    appendAssistantChunk(qc, 'c1', 'msg1', 'Hello ');
    appendAssistantChunk(qc, 'c1', 'msg1', 'world');
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].content).toBe('Hello world');
  });

  it('appendAssistantError adds an error message with unique id', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAssistantError(qc, 'c1', '⚠️ something went wrong');
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items).toHaveLength(1);
    expect(data?.items[0].content).toBe('⚠️ something went wrong');
    expect(data?.items[0].role).toBe('assistant');
  });

  it('appendAssistantReasoning appends delta to reasoning field', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAssistantStart(qc, 'c1', 'msg1');
    appendAssistantReasoning(qc, 'c1', 'msg1', '思考');
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].reasoning).toBe('思考');
    expect(data?.items[0].content).toBe('');
  });

  it('appendAgentMessageStart adds a blank agent message with empty agentBlocks', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAgentMessageStart(qc, 'c1', 'msg2');
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items).toHaveLength(1);
    expect(data?.items[0]).toMatchObject({
      id: 'msg2',
      role: 'assistant',
      content: '',
      agentBlocks: [],
    });
  });

  it('appendAgentBlock adds a block to agentBlocks array', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAgentMessageStart(qc, 'c1', 'msg2');
    appendAgentBlock(qc, 'c1', 'msg2', { type: 'thinking', content: 'analyzing...' });
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].agentBlocks).toHaveLength(1);
  expect(data?.items[0].agentBlocks?.[0]).toMatchObject({
      type: 'thinking',
      content: 'analyzing...',
    });
  });

  it('updateAgentBlock updates an existing block by index', () => {
  const qc = makeQc({ items: [], nextCursor: null });
    appendAgentMessageStart(qc, 'c1', 'msg2');
    appendAgentBlock(qc, 'c1', 'msg2', { type: 'tool_call', name: 'search', status: 'pending' });
    updateAgentBlock(qc, 'c1', 'msg2', 0, { status: 'completed', result: 'found 3 items' });
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].agentBlocks?.[0]).toMatchObject({
      type: 'tool_call',
      name: 'search',
      status: 'completed',
      result: 'found 3 items',
    });
  });

  it('markAgentMessageInterrupted sets interrupted flag to true', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAgentMessageStart(qc, 'c1', 'msg2');
    markAgentMessageInterrupted(qc, 'c1', 'msg2');
    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].interrupted).toBe(true);
  });

  it('upsertAgentBlock accumulates response block content', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAgentMessageStart(qc, 'c1', 'msg2');

    // First response chunk
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'response', content: 'Hello ' },
    });

    // Second response chunk should accumulate
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'response', content: 'world' },
    });

    // Third response chunk should accumulate
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'response', content: '!' },
    });

    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].agentBlocks).toHaveLength(1);
    expect(data?.items[0].agentBlocks?.[0]).toMatchObject({
      type: 'response',
      content: 'Hello world!',
    });
  });

  it('upsertAgentBlock creates new response block after non-response block', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAgentMessageStart(qc, 'c1', 'msg2');

    // Add a thinking block
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'thinking', content: 'analyzing...' },
    });

    // Add response block - should create new block, not accumulate
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'response', content: 'Result: ' },
    });

    // Add another response chunk - should accumulate to previous response
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'response', content: 'success' },
    });

    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].agentBlocks).toHaveLength(2);
    expect(data?.items[0].agentBlocks?.[0]).toMatchObject({
    type: 'thinking',
      content: 'analyzing...',
    });
    expect(data?.items[0].agentBlocks?.[1]).toMatchObject({
      type: 'response',
      content: 'Result: success',
    });
  });

  it('upsertAgentBlock updates tool_call blocks by toolCallId', () => {
    const qc = makeQc({ items: [], nextCursor: null });
    appendAgentMessageStart(qc, 'c1', 'msg2');

    // Add tool_call with toolCallId
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'tool_call', name: 'search', status: 'running' },
      toolCallId: 'tc1',
    });

    // Update same tool_call
    upsertAgentBlock(qc, 'c1', 'msg2', {
      block: { type: 'tool_call', name: 'search', status: 'completed', result: 'found items' },
      toolCallId: 'tc1',
    });

    const data = qc.getQueryData<MessagesPage>(['messages', 'c1']);
    expect(data?.items[0].agentBlocks).toHaveLength(1);
    expect(data?.items[0].agentBlocks?.[0]).toMatchObject({
      type: 'tool_call',
      name: 'search',
      status: 'completed',
      result: 'found items',
    });
  });
});
