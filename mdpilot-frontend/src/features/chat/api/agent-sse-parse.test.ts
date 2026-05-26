import { describe, expect, it } from 'vitest';

import { parseAgentSseFrames } from './agent-sse-parse';

describe('parseAgentSseFrames', () => {
  it('parses complete named SSE frames', () => {
    const chunk = 'event: thinking\ndata: {"content":"analyzing"}\n\n';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(1);
    expect(result.events[0]).toEqual({
      event: 'thinking',
      data: { content: 'analyzing' },
    });
    expect(result.buffer).toBe('');
  });

  it('parses multiple frames in one chunk', () => {
    const chunk =
      'event: thinking\ndata: {"content":"step1"}\n\n' +
      'event: tool_call\ndata: {"tool":"alphafold2"}\n\n';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(2);
    expect(result.events[0]).toEqual({
      event: 'thinking',
      data: { content: 'step1' },
    });
    expect(result.events[1]).toEqual({
      event: 'tool_call',
    data: { tool: 'alphafold2' },
    });
  });

  it('handles incomplete frame by returning buffer', () => {
    const chunk = 'event: thinking\ndata: {"content"';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(0);
    expect(result.buffer).toBe(chunk);
  });

  it('combines previous buffer with new chunk', () => {
    const buffer = 'event: thinking\ndata: {"con';
    const chunk = 'tent":"test"}\n\n';
    const result = parseAgentSseFrames(buffer, chunk);
    expect(result.events).toHaveLength(1);
    expect(result.events[0]).toEqual({
      event: 'thinking',
      data: { content: 'test' },
    });
    expect(result.buffer).toBe('');
  });
  it('returns empty events for malformed JSON data', () => {
    const chunk = 'event: thinking\ndata: {invalid json}\n\n';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(0);
    expect(result.buffer).toBe('');
  });

  it('skips frames without event name', () => {
    const chunk = 'data: {"content":"test"}\n\n';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(0);
  });

  it('skips frames without data', () => {
    const chunk = 'event: thinking\n\n';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(0);
  });

  it('handles mixed complete and incomplete frames', () => {
    const chunk =
      'event: thinking\ndata: {"content":"done"}\n\n' +
      'event: tool_call\ndata: {"tool"';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(1);
    expect(result.events[0]).toEqual({
      event: 'thinking',
      data: { content: 'done' },
    });
    expect(result.buffer).toBe('event: tool_call\ndata: {"tool"');
  });
  it('handles empty chunk', () => {
    const result = parseAgentSseFrames('', '');
    expect(result.events).toHaveLength(0);
    expect(result.buffer).toBe('');
  });

  it('handles chunk with only whitespace', () => {
    const result = parseAgentSseFrames('', '   \n\n  ');
    expect(result.events).toHaveLength(0);
    expect(result.buffer).toBe('');
  });

  it('parses error event', () => {
    const chunk = 'event: error\ndata: {"error":"agent execution failed"}\n\n';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(1);
    expect(result.events[0]).toEqual({
      event: 'error',
      data: { error: 'agent execution failed' },
    });
  });

  it('parses complete event', () => {
    const chunk = 'event: complete\ndata: {"result":"AlphaFold2 queued"}\n\n';
    const result = parseAgentSseFrames('', chunk);
    expect(result.events).toHaveLength(1);
    expect(result.events[0]).toEqual({
      event: 'complete',
      data: { result: 'AlphaFold2 queued' },
    });
  });

  it('parses tool_result event', () => {
    const chunk = 'event: tool_result\ndata: {"content":"queued"}\n\n';
    const result = parseAgentSseFrames('', chunk);
  expect(result.events).toHaveLength(1);
    expect(result.events[0]).toEqual({
      event: 'tool_result',
      data: { content: 'queued' },
    });
  });
});
