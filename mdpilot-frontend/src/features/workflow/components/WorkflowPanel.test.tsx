import { render, screen } from '@testing-library/react';
import { beforeEach,describe, expect, it } from 'vitest';

import { useWorkflowStore } from '../store/workflow.store';
import type { ToolExecution } from '../types';
import { WorkflowPanel } from './WorkflowPanel';

describe('WorkflowPanel', () => {
  beforeEach(() => {
    useWorkflowStore.getState().clearTools();
  });

  it('renders empty state when no tools', () => {
  render(<WorkflowPanel />);
    expect(screen.getByText('No tasks in queue')).toBeInTheDocument();
  });

  it('renders workflow header with statistics', () => {
    const tool: ToolExecution = {
      id: 'tool-1',
      name: 'alphafold2_predict',
    status: 'running',
      startTime: Date.now(),
  params: {},
    };
    useWorkflowStore.getState().addTool(tool);
    render(<WorkflowPanel />);
    expect(screen.getByText(/Total: 1/)).toBeInTheDocument();
    expect(screen.getByText(/Running: 1/)).toBeInTheDocument();
  });

  it('renders tool cards', () => {
    const tool: ToolExecution = {
      id: 'tool-1',
      name: 'alphafold2_predict',
      status: 'completed',
      startTime: Date.now(),
    params: {},
    };
    useWorkflowStore.getState().addTool(tool);
    render(<WorkflowPanel />);
    expect(screen.getByText(/alphafold2_predict/)).toBeInTheDocument();
  });
});
