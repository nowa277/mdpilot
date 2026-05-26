import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ToolExecution } from '../types';
import { BashCard } from './BashCard';

describe('BashCard', () => {
  const baseBashTool: ToolExecution = {
    id: 'bash-1',
    name: 'bash_run',
    status: 'pending',
    startTime: Date.now(),
    params: { command: 'ls -la' },
  };

  it('renders bash_run with 💻 icon', () => {
    render(<BashCard tool={baseBashTool} />);
    expect(screen.getByText(/💻 bash_run/)).toBeInTheDocument();
  });

  it('renders ssh_bash with 🖥️ icon', () => {
    const sshTool: ToolExecution = {
      ...baseBashTool,
      name: 'ssh_bash',
    };
    render(<BashCard tool={sshTool} />);
    expect(screen.getByText(/🖥️ ssh_bash/)).toBeInTheDocument();
  });

  it('renders command from params', () => {
    render(<BashCard tool={baseBashTool} />);
    expect(screen.getByText('ls -la')).toBeInTheDocument();
  });

  it('renders node info for SSH commands', () => {
    const sshTool: ToolExecution = {
      ...baseBashTool,
      name: 'ssh_bash',
      params: { command: 'pwd', node: 'lab02' },
    };
    render(<BashCard tool={sshTool} />);
    expect(screen.getByText(/Node:/)).toBeInTheDocument();
    expect(screen.getByText(/lab02/)).toBeInTheDocument();
  });

  it('renders progress bar when running', () => {
    const runningTool: ToolExecution = {
      ...baseBashTool,
      status: 'running',
      progress: { percent: 50, stage: 'Executing', eta: 30 },
    };
    render(<BashCard tool={runningTool} />);
    expect(screen.getByText('Progress: 50%')).toBeInTheDocument();
  });

  it('renders stdout output when available', () => {
    const toolWithOutput: ToolExecution = {
      ...baseBashTool,
      status: 'completed',
      result: { stdout: 'total 48\ndrwxr-xr-x 12 user user 4096' },
    };
    render(<BashCard tool={toolWithOutput} />);
    expect(screen.getByText(/stdout/)).toBeInTheDocument();
    expect(screen.getByText(/total 48/)).toBeInTheDocument();
  });

  it('renders stderr output with red background', () => {
    const toolWithError: ToolExecution = {
      ...baseBashTool,
      status: 'completed',
      result: { stderr: 'Permission denied' },
    };
    render(<BashCard tool={toolWithError} />);
    expect(screen.getByText(/stderr/)).toBeInTheDocument();
    expect(screen.getByText('Permission denied')).toBeInTheDocument();
  });

  it('renders error message when failed', () => {
    const failedTool: ToolExecution = {
      ...baseBashTool,
      status: 'failed',
      error: 'Command execution failed',
    };
    render(<BashCard tool={failedTool} />);
    expect(screen.getByText('Command execution failed')).toBeInTheDocument();
  });

  it('renders exit code when available', () => {
    const toolWithExitCode: ToolExecution = {
      ...baseBashTool,
      status: 'completed',
      result: { exit_code: 0 },
    };
    render(<BashCard tool={toolWithExitCode} />);
    expect(screen.getByText(/Exit code:/)).toBeInTheDocument();
    expect(screen.getByText(/0/)).toBeInTheDocument();
  });

  it('renders duration when completed', () => {
    const completedTool: ToolExecution = {
      ...baseBashTool,
      status: 'completed',
      duration: 1234,
    };
    render(<BashCard tool={completedTool} />);
    expect(screen.getByText(/Duration:/)).toBeInTheDocument();
    expect(screen.getByText(/1\.2s/)).toBeInTheDocument();
  });

  it('applies blue gradient background', () => {
    const { container } = render(<BashCard tool={baseBashTool} />);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('bg-gradient-to-br');
    expect(card.className).toContain('from-blue-50');
  });

  it('truncates long stdout with scrollable container', () => {
    const longOutput = Array(50).fill('line of output').join('\n');
    const toolWithLongOutput: ToolExecution = {
    ...baseBashTool,
      status: 'completed',
      result: { stdout: longOutput },
    };
    const { container } = render(<BashCard tool={toolWithLongOutput} />);
    const outputContainer = container.querySelector('.max-h-32');
    expect(outputContainer).toBeInTheDocument();
  });
});
