import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ProgressBar } from './ProgressBar';

describe('ProgressBar', () => {
  it('renders progress percentage', () => {
    render(<ProgressBar percent={75} stage="Executing" eta={30} />);
    expect(screen.getByText('Progress: 75%')).toBeInTheDocument();
  });

  it('renders stage label', () => {
    render(<ProgressBar percent={50} stage="ESM2 embedding" eta={60} />);
    expect(screen.getByText(/ESM2 embedding/)).toBeInTheDocument();
  });

  it('renders ETA', () => {
    render(<ProgressBar percent={25} stage="Running" eta={120} />);
    expect(screen.getByText('ETA: ~2m')).toBeInTheDocument();
  });

  it('formats ETA in seconds', () => {
    render(<ProgressBar percent={90} stage="Finalizing" eta={45} />);
  expect(screen.getByText('ETA: ~45s')).toBeInTheDocument();
  });
});
