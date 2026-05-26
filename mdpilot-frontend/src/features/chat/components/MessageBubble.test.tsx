import type { ChatMessage } from '@shared/types';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MessageBubble } from './MessageBubble';

const base: ChatMessage = {
  id: 'm1',
  chatId: 'c1',
  role: 'user',
  content: 'hello',
  createdAt: '2026-05-14T08:00:00Z',
};

describe('MessageBubble', () => {
  it('renders user content', () => {
    render(<MessageBubble message={base} />);
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('aligns user vs assistant differently', () => {
    const { container, rerender } = render(<MessageBubble message={base} />);
    expect(container.firstElementChild).toHaveAttribute('data-role', 'user');
    rerender(<MessageBubble message={{ ...base, role: 'assistant' }} />);
    expect(container.firstElementChild).toHaveAttribute('data-role', 'assistant');
  });
  it('renders markdown for assistant messages', () => {
    render(<MessageBubble message={{ ...base, role: 'assistant', content: '**bold**' }} />);
    expect(screen.getByText('bold').tagName.toLowerCase()).toBe('strong');
  });

  it('does not render ThinkingBlock when reasoning is absent', () => {
    render(<MessageBubble message={{ ...base, role: 'assistant', content: 'answer' }} />);
    expect(screen.queryByText('Thinking')).not.toBeInTheDocument();
  });

  it('renders ThinkingBlock (collapsed) alongside content when both are present', () => {
    render(
      <MessageBubble
        message={{ ...base, role: 'assistant', content: 'answer', reasoning: 'some thinking' }}
      />,
    );
    expect(screen.getByText('Thinking')).toBeInTheDocument();
    expect(screen.queryByText('some thinking')).not.toBeInTheDocument();
    expect(screen.getByText('answer')).toBeInTheDocument();
  });

  it('renders ThinkingBlock open and no MarkdownRenderer when only reasoning is present', () => {
    render(
      <MessageBubble
        message={{ ...base, role: 'assistant', content: '', reasoning: 'thinking...' }}
      />,
    );
    expect(screen.getByText('Thinking')).toBeInTheDocument();
    expect(screen.getByText('thinking...')).toBeInTheDocument();
  });

  it('should apply agent-message class to assistant messages', () => {
    const message: ChatMessage = {
      id: '2',
      chatId: 'chat1',
      role: 'assistant',
      content: 'Hello',
      createdAt: '2026-05-15T10:00:00Z',
    };

    const { container } = render(<MessageBubble message={message} />);
    const messageDiv = container.querySelector('.agent-message');

    expect(messageDiv).toBeInTheDocument();
  });
});
