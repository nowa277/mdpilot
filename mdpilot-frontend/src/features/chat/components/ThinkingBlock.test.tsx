import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ThinkingBlock } from './ThinkingBlock';

describe('ThinkingBlock', () => {
  it('renders the header text', () => {
    render(<ThinkingBlock reasoning="some thinking" />);
    expect(screen.getByText('思考过程')).toBeInTheDocument();
  });

  it('hides content by default (collapsed)', () => {
    render(<ThinkingBlock reasoning="hidden content" />);
    expect(screen.queryByText('hidden content')).not.toBeInTheDocument();
  });

  it('expands to show reasoning when button is clicked', async () => {
    render(<ThinkingBlock reasoning="expanded content" />);
    await userEvent.click(screen.getByRole('button'));
    expect(screen.getByText('expanded content')).toBeInTheDocument();
  });

  it('collapses again on second click', async () => {
    render(<ThinkingBlock reasoning="toggle content" />);
    const btn = screen.getByRole('button');
    await userEvent.click(btn);
    expect(screen.getByText('toggle content')).toBeInTheDocument();
    await userEvent.click(btn);
    expect(screen.queryByText('toggle content')).not.toBeInTheDocument();
  });

  it('shows content immediately when defaultOpen is true', () => {
    render(<ThinkingBlock reasoning="visible content" defaultOpen />);
    expect(screen.getByText('visible content')).toBeInTheDocument();
  });
});
