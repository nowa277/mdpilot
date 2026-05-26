import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ToolExecution } from '../types';
import { DefaultCard } from './DefaultCard';

describe('DefaultCard', () => {
  const baseToolExecution: ToolExecution = {
    id: 'tool-1',
    name: 'unknown_tool',
    status: 'pending',
    startTime: Date.now(),
    params: { input: 'test' },
  };

  it('renders tool name', () => {
    render(<DefaultCard tool={baseToolExecution} />);
    expect(screen.getByText('unknown_tool')).toBeInTheDocument();
  });

  it('renders status badge', () => {
    render(<DefaultCard tool={{ ...baseToolExecution, status: 'running' }} />);
    expect(screen.getByText('⏳ Running')).toBeInTheDocument();
  });

  it('renders backend info when available', () => {
    const toolWithBackend: ToolExecution = {
      ...baseToolExecution,
    backend: { node: 'lab02', resources: '4 CPU, 16GB RAM' },
    };
    render(<DefaultCard tool={toolWithBackend} />);
    expect(screen.getByText(/lab02/)).toBeInTheDocument();
    expect(screen.getByText(/4 CPU, 16GB RAM/)).toBeInTheDocument();
  });

  it('renders progress bar when running', () => {
    const runningTool: ToolExecution = {
   ...baseToolExecution,
      status: 'running',
      progress: { percent: 65, stage: 'Processing', eta: 120 },
    };
    render(<DefaultCard tool={runningTool} />);
    expect(screen.getByText('Progress: 65%')).toBeInTheDocument();
    expect(screen.getByText(/Processing/)).toBeInTheDocument();
  });

  it('does not render progress bar when not running', () => {
    render(<DefaultCard tool={{ ...baseToolExecution, status: 'completed' }} />);
    expect(screen.queryByText(/Progress:/)).not.toBeInTheDocument();
  });

  it('renders parameters as JSON', () => {
    const toolWithParams: ToolExecution = {
    ...baseToolExecution,
      params: { input: 'test', count: 42 },
    };
    render(<DefaultCard tool={toolWithParams} />);
    expect(screen.getByText(/Parameters/)).toBeInTheDocument();
    expect(screen.getByText(/"input"/)).toBeInTheDocument();
    expect(screen.getByText(/"count"/)).toBeInTheDocument();
  });

  it('renders result when completed', () => {
    const completedTool: ToolExecution = {
      ...baseToolExecution,
      status: 'completed',
      result: { output: 'success', value: 100 },
    };
    render(<DefaultCard tool={completedTool} />);
    expect(screen.getByText(/Result/)).toBeInTheDocument();
    expect(screen.getByText(/"output"/)).toBeInTheDocument();
    expect(screen.getByText(/"success"/)).toBeInTheDocument();
  });

  it('renders error when failed', () => {
    const failedTool: ToolExecution = {
      ...baseToolExecution,
      status: 'failed',
      error: 'Connection timeout',
    };
    render(<DefaultCard tool={failedTool} />);
    expect(screen.getByText(/Error/)).toBeInTheDocument();
    expect(screen.getByText('Connection timeout')).toBeInTheDocument();
  });

  it('renders duration when completed', () => {
    const completedTool: ToolExecution = {
      ...baseToolExecution,
      status: 'completed',
      duration: 5432,
    };
    render(<DefaultCard tool={completedTool} />);
    expect(screen.getByText(/Duration:/)).toBeInTheDocument();
    expect(screen.getByText(/5\.4s/)).toBeInTheDocument();
  });

  it('renders elapsed time when running', () => {
    const runningTool: ToolExecution = {
      ...baseToolExecution,
      status: 'running',
      startTime: Date.now() - 3000,
    };
    render(<DefaultCard tool={runningTool} />);
    expect(screen.getByText(/Elapsed:/)).toBeInTheDocument();
  });

  it('applies gray gradient background', () => {
    const { container } = render(<DefaultCard tool={baseToolExecution} />);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('bg-gradient-to-br');
    expect(card.className).toContain('from-gray-50');
  });
});
