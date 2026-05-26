import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ToolExecution } from '../types';
import { BioReasonCard } from './BioReasonCard';

describe('BioReasonCard', () => {
  const baseTool: ToolExecution = {
    id: '1',
    name: 'bioreason_annotate',
    status: 'completed',
    startTime: Date.now() - 45000,
    endTime: Date.now(),
    duration: 45,
    params: {},
    result: {
      go_terms: {
        total: 93,
        MF: 32,
        BP: 45,
        CC: 16,
      },
    },
    backend: {
    node: 'lab06',
      resources: '9×RTX 3090',
    },
  };

  it('renders tool name with microscope icon', () => {
    render(<BioReasonCard tool={baseTool} />);
    expect(screen.getByText(/🔬.*BioReason Annotate/)).toBeInTheDocument();
  });

  it('renders total GO terms count', () => {
    render(<BioReasonCard tool={baseTool} />);
    expect(screen.getByText(/93 total/)).toBeInTheDocument();
  });

  it('renders Molecular Function count', () => {
    render(<BioReasonCard tool={baseTool} />);
    expect(screen.getByText('Molecular Function (MF)')).toBeInTheDocument();
    expect(screen.getByText('32')).toBeInTheDocument();
  });

  it('renders Biological Process count', () => {
    render(<BioReasonCard tool={baseTool} />);
    expect(screen.getByText('Biological Process (BP)')).toBeInTheDocument();
    expect(screen.getByText('45')).toBeInTheDocument();
  });

  it('renders Cellular Component count', () => {
    render(<BioReasonCard tool={baseTool} />);
    expect(screen.getByText('Cellular Component (CC)')).toBeInTheDocument();
    expect(screen.getByText('16')).toBeInTheDocument();
  });
});
