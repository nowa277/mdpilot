import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ToolExecution } from '../types';
import { AmberCard } from './AmberCard';

describe('AmberCard', () => {
  const mockTool: ToolExecution = {
    id: 'tool-1',
    name: 'amber_minimize',
    status: 'completed',
    startTime: Date.now() - 720000,
    endTime: Date.now(),
    duration: 720000,
    params: {
      steps: 5000,
      method: 'steepest descent',
      convergence: 0.01,
    },
    result: {
      final_energy: -12345.67,
    },
    backend: { node: 'lab03', resources: '16×CPU' },
  };

  it('renders tool name with icon', () => {
    render(<AmberCard tool={mockTool} />);
    expect(screen.getByText(/⚗️ AMBER Minimize/)).toBeInTheDocument();
  });

  it('renders parameters', () => {
    render(<AmberCard tool={mockTool} />);
    expect(screen.getByText('Steps:')).toBeInTheDocument();
    expect(screen.getByText('5000')).toBeInTheDocument();
    expect(screen.getByText('Method:')).toBeInTheDocument();
    expect(screen.getByText('steepest descent')).toBeInTheDocument();
  });

  it('renders final energy', () => {
    render(<AmberCard tool={mockTool} />);
    expect(screen.getByText(/-12345.67/)).toBeInTheDocument();
  });
});
