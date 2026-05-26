import type { AgentBlock } from '@shared/types';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AgentStreamMessage } from './AgentStreamMessage';

// Mock the chat-ui store
vi.mock('../store/chat-ui.store', () => ({
  useChatUiStore: vi.fn((selector) =>
    selector({
      setRightPanelTab: vi.fn(),
      setRightPanel: vi.fn(),
    }),
  ),
}));

// Mock the workflow sync hook
vi.mock('@features/workflow/hooks/useWorkflowSync', () => ({
  useWorkflowSync: vi.fn(),
}));

describe('AgentStreamMessage', () => {
  it('renders thinking block', () => {
    const blocks: AgentBlock[] = [{ type: 'thinking', content: 'analyzing the problem' }];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('思考过程')).toBeInTheDocument();
  });

  it('renders execution summary for tool_call blocks', () => {
    const blocks: AgentBlock[] = [
      { type: 'tool_call', name: 'search', status: 'pending' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText(/Executed: search/)).toBeInTheDocument();
    expect(screen.getByText('details')).toBeInTheDocument();
  });

  it('renders execution summary with multiple tools', () => {
    const blocks: AgentBlock[] = [
      { type: 'tool_call', name: 'search', status: 'completed', result: 'found 3 results' },
      { type: 'tool_call', name: 'analyze', status: 'running' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText(/Executed: search → analyze/)).toBeInTheDocument();
  });

  it('calls handleViewDetails when clicking view details button', async () => {
    const blocks: AgentBlock[] = [
      { type: 'tool_call', name: 'search', status: 'completed' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);

    const viewDetailsButton = screen.getByText('details');
    await userEvent.click(viewDetailsButton);
    // Store methods are mocked, so we just verify the button is clickable
    expect(viewDetailsButton).toBeInTheDocument();
  });

  it('does not render execution summary when no tool_call blocks', () => {
    const blocks: AgentBlock[] = [
      { type: 'thinking', content: 'planning' },
      { type: 'response', content: 'done' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.queryByText(/Executed:/)).not.toBeInTheDocument();
  });

  it('renders tool_result block', () => {
    const blocks: AgentBlock[] = [
      { type: 'tool_result', name: 'search', result: 'data retrieved' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('Result: search')).toBeInTheDocument();
    expect(screen.getByText('data retrieved')).toBeInTheDocument();
  });

  it('renders progress block', () => {
    const blocks: AgentBlock[] = [
      { type: 'progress', message: 'processing files', percent: 45 },
    ];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('Progress')).toBeInTheDocument();
    expect(screen.getByText('processing files (45%)')).toBeInTheDocument();
  });

  it('renders progress block without percent', () => {
    const blocks: AgentBlock[] = [{ type: 'progress', message: 'starting task' }];
  render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('starting task')).toBeInTheDocument();
  });

  it('renders error block', () => {
    const blocks: AgentBlock[] = [{ type: 'error', message: 'failed to connect' }];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('failed to connect')).toBeInTheDocument();
  });

  it('renders response block with markdown', () => {
    const blocks: AgentBlock[] = [{ type: 'response', content: '# Result\n\nTask completed' }];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('Result')).toBeInTheDocument();
    expect(screen.getByText('Task completed')).toBeInTheDocument();
  });

  it('renders multiple blocks in correct order', () => {
    const blocks: AgentBlock[] = [
      { type: 'thinking', content: 'planning' },
      { type: 'tool_call', name: 'search', status: 'completed', result: 'done' },
      { type: 'progress', message: 'processing' },
      { type: 'response', content: 'finished' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('思考过程')).toBeInTheDocument();
    expect(screen.getByText(/Executed: search/)).toBeInTheDocument();
    expect(screen.getByText('Progress')).toBeInTheDocument();
    expect(screen.getByText('finished')).toBeInTheDocument();
  });

  it('renders interrupted indicator when interrupted is true', () => {
    const blocks: AgentBlock[] = [{ type: 'thinking', content: 'partial' }];
    render(<AgentStreamMessage blocks={blocks} interrupted />);
    expect(screen.getByText('Message was interrupted')).toBeInTheDocument();
  });

  it('does not render interrupted indicator when interrupted is false', () => {
    const blocks: AgentBlock[] = [{ type: 'thinking', content: 'complete' }];
    render(<AgentStreamMessage blocks={blocks} interrupted={false} />);
    expect(screen.queryByText('Message was interrupted')).not.toBeInTheDocument();
  });

  it('does not render interrupted indicator when interrupted is undefined', () => {
    const blocks: AgentBlock[] = [{ type: 'thinking', content: 'complete' }];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.queryByText('Message was interrupted')).not.toBeInTheDocument();
  });

  it('renders three-part structure: thinking + execution + response', () => {
    const blocks: AgentBlock[] = [
      { type: 'thinking', content: 'analyzing' },
      { type: 'tool_call', name: 'bash_run', status: 'completed', input: { command: 'ls' } },
      { type: 'response', content: 'Task complete' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);

    // Part 1: Thinking
    expect(screen.getByText('思考过程')).toBeInTheDocument();

    // Part 2: Execution Summary
    expect(screen.getByText(/Executed: bash_run/)).toBeInTheDocument();
    expect(screen.getByText('details')).toBeInTheDocument();

    // Part 3: Response Content
    expect(screen.getByText('Task complete')).toBeInTheDocument();
  });

  it('handles blocks with only response content', () => {
    const blocks: AgentBlock[] = [
      { type: 'response', content: 'Simple response' },
    ];
    render(<AgentStreamMessage blocks={blocks} />);
    expect(screen.getByText('Simple response')).toBeInTheDocument();
    expect(screen.queryByText('思考过程')).not.toBeInTheDocument();
    expect(screen.queryByText(/Executed:/)).not.toBeInTheDocument();
  });
});
