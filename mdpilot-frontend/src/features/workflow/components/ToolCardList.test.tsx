import { render, screen } from '@testing-library/react';
import { describe, expect,it } from 'vitest';

import type { ToolExecution } from '../types';
import { ToolCardList } from './ToolCardList';

describe('ToolCardList', () => {
  it('renders empty state when no tools provided', () => {
    render(<ToolCardList tools={[]} />);
    expect(screen.getByText('No tools to display')).toBeInTheDocument();
  });

  it('renders a list of tool cards', () => {
    const tools: ToolExecution[] = [
      {
        id: '1',
        name: 'bash_run',
        status: 'completed',
        startTime: Date.now(),
        params: {},
      },
      {
        id: '2',
        name: 'alphafold2_predict',
        status: 'running',
        startTime: Date.now(),
     params: {},
      },
    ];

    render(<ToolCardList tools={tools} />);

    // Check that both tools are rendered
    expect(screen.getByText(/bash_run/i)).toBeInTheDocument();
    expect(screen.getByText(/alphafold2_predict/i)).toBeInTheDocument();
  });

  it('renders correct number of tool cards', () => {
    const tools: ToolExecution[] = Array.from({ length: 5 }, (_, i) => ({
      id: `${i}`,
      name: 'bash_run',
      status: 'completed' as const,
      startTime: Date.now(),
      params: {},
    }));

    const { container } = render(<ToolCardList tools={tools} />);

    // Count the number of tool card containers
    const toolCards = container.querySelectorAll('[data-testid="tool-card"]');
    expect(toolCards).toHaveLength(5);
  });

  it('renders tools in the correct order', () => {
    const tools: ToolExecution[] = [
      {
        id: '1',
        name: 'bash_run',
        status: 'completed',
        startTime: Date.now(),
    params: {},
      },
      {
        id: '2',
        name: 'alphafold2_predict',
        status: 'running',
        startTime: Date.now(),
      params: {},
      },
      {
        id: '3',
        name: 'amber_minimize',
        status: 'pending',
        startTime: Date.now(),
        params: {},
      },
    ];

    const { container } = render(<ToolCardList tools={tools} />);
    const toolCards = container.querySelectorAll('[data-testid="tool-card"]');

    // Verify cards are rendered in order by checking they exist
    expect(toolCards).toHaveLength(3);
    // Verify each card contains the tool name or its rendered label
    expect(toolCards[0]).toHaveTextContent(/bash_run|Bash/i);
    expect(toolCards[1]).toHaveTextContent(/alphafold2|AlphaFold/i);
    expect(toolCards[2]).toHaveTextContent(/amber|AMBER/i);
  });

  it('handles single tool', () => {
    const tools: ToolExecution[] = [
      {
      id: '1',
        name: 'bash_run',
        status: 'completed',
        startTime: Date.now(),
        params: {},
      },
    ];

    const { container } = render(<ToolCardList tools={tools} />);
    const toolCards = container.querySelectorAll('[data-testid="tool-card"]');

    expect(toolCards).toHaveLength(1);
  });
});
