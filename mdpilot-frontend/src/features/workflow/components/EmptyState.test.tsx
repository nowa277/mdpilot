import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('renders empty state message', () => {
    render(<EmptyState />);
    expect(screen.getByText('No tasks in queue')).toBeInTheDocument();
  });
  it('renders sparkle icon', () => {
    render(<EmptyState />);
    expect(screen.getByText('✨')).toBeInTheDocument();
  });
});
