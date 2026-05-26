import { beforeEach,describe, expect, it } from 'vitest';

import type { ToolExecution } from '../types';
import { useWorkflowStore } from './workflow.store';

describe('useWorkflowStore', () => {
  beforeEach(() => {
    useWorkflowStore.getState().clearTools();
  });

  it('initializes with empty tools array', () => {
    const { tools } = useWorkflowStore.getState();
    expect(tools).toEqual([]);
  });

  it('adds a tool', () => {
    const tool: ToolExecution = {
      id: 'tool-1',
      name: 'alphafold2_predict',
      status: 'running',
      startTime: Date.now(),
      params: { sequence: 'MKTAYIAKQR' },
    };

    useWorkflowStore.getState().addTool(tool);
    const { tools } = useWorkflowStore.getState();

    expect(tools).toHaveLength(1);
    expect(tools[0]).toEqual(tool);
  });

  it('updates tool progress', () => {
    const tool: ToolExecution = {
      id: 'tool-1',
      name: 'alphafold2_predict',
      status: 'running',
      startTime: Date.now(),
      params: {},
    };

    useWorkflowStore.getState().addTool(tool);
    useWorkflowStore.getState().updateToolProgress('tool-1', {
      percent: 75,
      stage: 'Executing',
      eta: 30,
    });

    const { tools } = useWorkflowStore.getState();
    expect(tools[0].progress).toEqual({
      percent: 75,
      stage: 'Executing',
      eta: 30,
    });
  });

  it('completes a tool', () => {
    const tool: ToolExecution = {
      id: 'tool-1',
      name: 'alphafold2_predict',
      status: 'running',
      startTime: Date.now(),
      params: {},
    };

    useWorkflowStore.getState().addTool(tool);
    useWorkflowStore.getState().completeTool('tool-1', { plddt: 92.3 }, 3600000, ['/output/model.pdb']);

    const { tools } = useWorkflowStore.getState();
    expect(tools[0].status).toBe('completed');
    expect(tools[0].result).toEqual({ plddt: 92.3 });
    expect(tools[0].duration).toBe(3600000);
    expect(tools[0].outputFiles).toEqual(['/output/model.pdb']);
    expect(tools[0].endTime).toBeDefined();
  });

  it('fails a tool', () => {
    const tool: ToolExecution = {
      id: 'tool-1',
      name: 'alphafold2_predict',
      status: 'running',
      startTime: Date.now(),
      params: {},
    };

    useWorkflowStore.getState().addTool(tool);
    useWorkflowStore.getState().failTool('tool-1', 'CUDA out of memory');

    const { tools } = useWorkflowStore.getState();
    expect(tools[0].status).toBe('failed');
    expect(tools[0].error).toBe('CUDA out of memory');
    expect(tools[0].endTime).toBeDefined();
  });

  it('clears all tools', () => {
    const tool: ToolExecution = {
      id: 'tool-1',
      name: 'alphafold2_predict',
      status: 'completed',
      startTime: Date.now(),
      params: {},
    };

    useWorkflowStore.getState().addTool(tool);
    useWorkflowStore.getState().clearTools();
    const { tools } = useWorkflowStore.getState();
    expect(tools).toEqual([]);
  });
});
