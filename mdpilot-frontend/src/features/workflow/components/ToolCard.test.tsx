import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ToolExecution } from '../types';
import { ToolCard } from './ToolCard';

describe('ToolCard', () => {
  const baseToolExecution: ToolExecution = {
    id: 'tool-1',
    name: 'unknown_tool',
    status: 'pending',
    startTime: Date.now(),
    params: {},
  };

  it('renders AlphaFold2Card for alphafold2_predict tool', () => {
    const alphafold2Tool: ToolExecution = {
      ...baseToolExecution,
      name: 'alphafold2_predict',
      params: { sequence: 'MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL' },
      status: 'completed',
      result: { plddt_scores: [85, 88, 82, 90, 87] },
    };
    render(<ToolCard tool={alphafold2Tool} />);
    expect(screen.getByText(/🧬.*alphafold2_predict/)).toBeInTheDocument();
  });

  it('renders BioReasonCard for bioreason_annotate tool', () => {
    const bioreasonTool: ToolExecution = {
      ...baseToolExecution,
      name: 'bioreason_annotate',
      params: { protein_id: 'P12345' },
      status: 'completed',
      result: { go_terms: { total: 10, MF: 3, BP: 5, CC: 2 } },
    };
    render(<ToolCard tool={bioreasonTool} />);
    expect(screen.getByText(/🔬 BioReason Annotate/)).toBeInTheDocument();
  });

  it('renders AmberCard for amber_minimize tool', () => {
    const amberTool: ToolExecution = {
      ...baseToolExecution,
      name: 'amber_minimize',
      params: { pdb_file: 'protein.pdb' },
   status: 'completed',
    };
    render(<ToolCard tool={amberTool} />);
    expect(screen.getByText(/⚗️ AMBER Minimize/)).toBeInTheDocument();
  });

  it('renders AmberCard for amber_heat tool', () => {
    const amberTool: ToolExecution = {
      ...baseToolExecution,
      name: 'amber_heat',
      params: { pdb_file: 'protein.pdb' },
      status: 'completed',
    };
    render(<ToolCard tool={amberTool} />);
    expect(screen.getByText(/⚗️ AMBER Heat/)).toBeInTheDocument();
  });

  it('renders AmberCard for amber_equilibrate tool', () => {
    const amberTool: ToolExecution = {
      ...baseToolExecution,
      name: 'amber_equilibrate',
      params: { pdb_file: 'protein.pdb' },
      status: 'completed',
    };
    render(<ToolCard tool={amberTool} />);
    expect(screen.getByText(/⚗️ AMBER Equilibrate/)).toBeInTheDocument();
  });

  it('renders AmberCard for amber_production tool', () => {
    const amberTool: ToolExecution = {
      ...baseToolExecution,
      name: 'amber_production',
      params: { pdb_file: 'protein.pdb' },
      status: 'completed',
    };
    render(<ToolCard tool={amberTool} />);
    expect(screen.getByText(/⚗️ AMBER Production/)).toBeInTheDocument();
  });

  it('renders BashCard for bash_run tool', () => {
    const bashTool: ToolExecution = {
      ...baseToolExecution,
      name: 'bash_run',
      params: { command: 'ls -la' },
      status: 'completed',
      result: { stdout: 'output' },
    };
    render(<ToolCard tool={bashTool} />);
    expect(screen.getByText(/💻 bash_run/)).toBeInTheDocument();
  });

  it('renders BashCard for ssh_bash tool', () => {
    const bashTool: ToolExecution = {
      ...baseToolExecution,
      name: 'ssh_bash',
      params: { command: 'ls -la' },
      status: 'completed',
      result: { stdout: 'output' },
    };
    render(<ToolCard tool={bashTool} />);
    expect(screen.getByText(/🖥️ ssh_bash/)).toBeInTheDocument();
  });

  it('renders DefaultCard for unknown tool', () => {
    const unknownTool: ToolExecution = {
      ...baseToolExecution,
      name: 'unknown_tool',
      params: { input: 'test' },
    };
    render(<ToolCard tool={unknownTool} />);
    expect(screen.getByText('unknown_tool')).toBeInTheDocument();
  });

  it('renders DefaultCard for tool without specific renderer', () => {
    const customTool: ToolExecution = {
      ...baseToolExecution,
    name: 'custom_analysis',
      params: { data: 'test' },
    };
    render(<ToolCard tool={customTool} />);
    expect(screen.getByText('custom_analysis')).toBeInTheDocument();
  });
});
