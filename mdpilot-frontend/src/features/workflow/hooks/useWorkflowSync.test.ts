import type { AgentBlock } from '@shared/types';
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useWorkflowStore } from '../store/workflow.store';
import { useWorkflowSync } from './useWorkflowSync';

describe('useWorkflowSync', () => {
  beforeEach(() => {
    useWorkflowStore.getState().clearTools();
    vi.clearAllMocks();
  });

  it('does nothing when blocks array is empty', () => {
    const blocks: AgentBlock[] = [];
    renderHook(() => useWorkflowSync(blocks));

    const { tools } = useWorkflowStore.getState();
    expect(tools).toEqual([]);
  });

  it('ignores non-tool_call blocks', () => {
    const blocks: AgentBlock[] = [
      { type: 'thinking', content: 'Analyzing...' },
      { type: 'response', content: 'Done' },
    ];
    renderHook(() => useWorkflowSync(blocks));

    const { tools } = useWorkflowStore.getState();
    expect(tools).toEqual([]);
  });

  it('adds pending tool_call blocks to store', () => {
    const blocks: AgentBlock[] = [
      {
        type: 'tool_call',
        name: 'alphafold2_predict',
        status: 'pending',
        input: { sequence: 'MKTAYIAKQR' },
      },
    ];

    renderHook(() => useWorkflowSync(blocks));

    const { tools } = useWorkflowStore.getState();
    expect(tools).toHaveLength(1);
    expect(tools[0].name).toBe('alphafold2_predict');
    expect(tools[0].status).toBe('pending');
    expect(tools[0].params).toEqual({ sequence: 'MKTAYIAKQR' });
  });

  it('updates tool status from pending to running', () => {
    const pendingBlocks: AgentBlock[] = [
      {
        type: 'tool_call',
        name: 'alphafold2_predict',
        status: 'pending',
        input: { sequence: 'MKTAYIAKQR' },
      },
    ];

    const { rerender } = renderHook(({ blocks }) => useWorkflowSync(blocks), {
      initialProps: { blocks: pendingBlocks },
    });

    const runningBlocks: AgentBlock[] = [
      {
        type: 'tool_call',
        name: 'alphafold2_predict',
        status: 'running',
        input: { sequence: 'MKTAYIAKQR' },
      },
    ];

    rerender({ blocks: runningBlocks });

    const { tools } = useWorkflowStore.getState();
    expect(tools).toHaveLength(1);
    expect(tools[0].status).toBe('running');
  });

  it('completes tool when status changes to completed', () => {
    const pendingBlocks: AgentBlock[] = [
      {
     type: 'tool_call',
        name: 'alphafold2_predict',
        status: 'pending',
        input: { sequence: 'MKTAYIAKQR' },
      },
    ];

    const { rerender } = renderHook(({ blocks }) => useWorkflowSync(blocks), {
      initialProps: { blocks: pendingBlocks },
    });

    const completedBlocks: AgentBlock[] = [
      {
        type: 'tool_call',
     name: 'alphafold2_predict',
        status: 'completed',
        input: { sequence: 'MKTAYIAKQR' },
        result: 'Success',
      },
    ];

    rerender({ blocks: completedBlocks });

    const { tools } = useWorkflowStore.getState();
    expect(tools).toHaveLength(1);
    expect(tools[0].status).toBe('completed');
  });

  it('fails tool when status changes to failed', () => {
    const pendingBlocks: AgentBlock[] = [
      {
        type: 'tool_call',
        name: 'alphafold2_predict',
        status: 'pending',
        input: { sequence: 'MKTAYIAKQR' },
      },
    ];

    const { rerender } = renderHook(({ blocks }) => useWorkflowSync(blocks), {
      initialProps: { blocks: pendingBlocks },
    });

    const failedBlocks: AgentBlock[] = [
      {
        type: 'tool_call',
        name: 'alphafold2_predict',
        status: 'failed',
        input: { sequence: 'MKTAYIAKQR' },
     error: 'CUDA out of memory',
      },
    ];

    rerender({ blocks: failedBlocks });

    const { tools } = useWorkflowStore.getState();
    expect(tools).toHaveLength(1);
    expect(tools[0].status).toBe('failed');
    expect(tools[0].error).toBe('CUDA out of memory');
  });

  it('handles multiple tool_call blocks', () => {
    const blocks: AgentBlock[] = [
      {
        type: 'tool_call',
        name: 'alphafold2_predict',
        status: 'completed',
        input: { sequence: 'MKTAYIAKQR' },
      },
      {
        type: 'tool_call',
        name: 'bioreason_analyze',
        status: 'running',
        input: { pdb_file: 'model.pdb' },
      },
    ];

    renderHook(() => useWorkflowSync(blocks));

    const { tools } = useWorkflowStore.getState();
    expect(tools).toHaveLength(2);
    expect(tools[0].name).toBe('alphafold2_predict');
    expect(tools[1].name).toBe('bioreason_analyze');
  });

  it('preserves backend information when available', () => {
    const blocks: AgentBlock[] = [
      {
        type: 'tool_call',
        name: 'alphafold2_predict',
      status: 'running',
        input: { sequence: 'MKTAYIAKQR' },
     backend: {
          node: 'lab02',
          gpuInfo: 'NVIDIA A100',
        },
      },
    ];

    renderHook(() => useWorkflowSync(blocks));

    const { tools } = useWorkflowStore.getState();
    expect(tools).toHaveLength(1);
    expect(tools[0].backend).toEqual({
    node: 'lab02',
      resources: 'NVIDIA A100',
    });
  });
});
