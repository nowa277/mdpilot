import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ToolExecution } from '../types';
import { AlphaFold2Card } from './AlphaFold2Card';

describe('AlphaFold2Card', () => {
  const baseToolExecution: ToolExecution = {
    id: 'af2-1',
    name: 'alphafold2_predict',
    status: 'pending',
    startTime: Date.now(),
    params: {
      sequence: 'MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL',
    },
  };

  it('renders tool name with DNA icon', () => {
    render(<AlphaFold2Card tool={baseToolExecution} />);
    expect(screen.getByText(/🧬 alphafold2_predict/)).toBeInTheDocument();
  });

  it('renders backend info when available', () => {
    const toolWithBackend: ToolExecution = {
      ...baseToolExecution,
      backend: { node: 'lab03', resources: '1 GPU, 32GB RAM' },
    };
    render(<AlphaFold2Card tool={toolWithBackend} />);
    expect(screen.getByText(/lab03/)).toBeInTheDocument();
    expect(screen.getByText(/1 GPU, 32GB RAM/)).toBeInTheDocument();
  });

  it('truncates long sequences to 50 characters', () => {
    const longSequence = 'A'.repeat(100);
    const toolWithLongSeq: ToolExecution = {
      ...baseToolExecution,
      params: { sequence: longSequence },
    };
    render(<AlphaFold2Card tool={toolWithLongSeq} />);
    expect(screen.getByText(/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\.\.\./)).toBeInTheDocument();
  });

  it('renders pLDDT scores for 5 models with color coding', () => {
    const completedTool: ToolExecution = {
      ...baseToolExecution,
      status: 'completed',
      result: {
     plddt_scores: [92.5, 88.3, 75.2, 68.9, 95.1],
      },
    };
    render(<AlphaFold2Card tool={completedTool} />);

    // Check all 5 models are displayed
    expect(screen.getByText(/Model 1/)).toBeInTheDocument();
    expect(screen.getByText(/Model 2/)).toBeInTheDocument();
    expect(screen.getByText(/Model 3/)).toBeInTheDocument();
    expect(screen.getByText(/Model 4/)).toBeInTheDocument();
    expect(screen.getByText(/Model 5/)).toBeInTheDocument();

    // Check scores are displayed
    expect(screen.getByText('92.5')).toBeInTheDocument();
    expect(screen.getByText('88.3')).toBeInTheDocument();
    expect(screen.getByText('75.2')).toBeInTheDocument();
    expect(screen.getByText('68.9')).toBeInTheDocument();
    expect(screen.getByText('95.1')).toBeInTheDocument();
  });

  it('highlights best model with star icon', () => {
    const completedTool: ToolExecution = {
      ...baseToolExecution,
      status: 'completed',
      result: {
        plddt_scores: [92.5, 88.3, 75.2, 68.9, 95.1],
      },
    };
    const { container } = render(<AlphaFold2Card tool={completedTool} />);

    // Model 5 has the highest score (95.1), should have star
    expect(container.textContent).toContain('Model 5 ⭐');
  });
  it('renders progress bar when running', () => {
    const runningTool: ToolExecution = {
   ...baseToolExecution,
      status: 'running',
      progress: { percent: 45, stage: 'Running MSA', eta: 300 },
    };
    render(<AlphaFold2Card tool={runningTool} />);
    expect(screen.getByText('Progress: 45%')).toBeInTheDocument();
    expect(screen.getByText(/Running MSA/)).toBeInTheDocument();
  });

  it('renders error when failed', () => {
    const failedTool: ToolExecution = {
   ...baseToolExecution,
      status: 'failed',
      error: 'GPU out of memory',
    };
    render(<AlphaFold2Card tool={failedTool} />);
    expect(screen.getByText(/Error/)).toBeInTheDocument();
    expect(screen.getByText('GPU out of memory')).toBeInTheDocument();
  });

  it('renders duration when completed', () => {
    const completedTool: ToolExecution = {
      ...baseToolExecution,
      status: 'completed',
      duration: 125000,
      result: { plddt_scores: [90, 85, 80, 75, 92] },
    };
    render(<AlphaFold2Card tool={completedTool} />);
    expect(screen.getByText(/Duration:/)).toBeInTheDocument();
    expect(screen.getByText(/2m 5s/)).toBeInTheDocument();
  });

  it('renders output files link when available', () => {
    const completedTool: ToolExecution = {
      ...baseToolExecution,
      status: 'completed',
      outputFiles: ['/path/to/model_1.pdb', '/path/to/model_2.pdb'],
      result: { plddt_scores: [90, 85, 80, 75, 92] },
    };
    render(<AlphaFold2Card tool={completedTool} />);
    expect(screen.getByText(/Output Files/)).toBeInTheDocument();
    expect(screen.getByText('2 files')).toBeInTheDocument();
  });

  it('applies green gradient background', () => {
    const { container } = render(<AlphaFold2Card tool={baseToolExecution} />);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('bg-gradient-to-br');
    expect(card.className).toContain('from-green-50');
  });
});
