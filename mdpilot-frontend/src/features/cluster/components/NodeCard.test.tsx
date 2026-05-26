import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { NodeStatus } from '../types';
import { NodeCard } from './NodeCard';

const onlineNode: NodeStatus = {
  id: 'lab02',
  online: true,
  gpu: { id: 'gpu-lab02-0', model: 'NVIDIA A100 80GB', usedMB: 6_400, totalMB: 81_920 },
  queueDepth: 1,
  lastSeen: '2026-05-14T10:00:00Z',
};

const offlineNode: NodeStatus = {
  id: 'lab06',
  online: false,
  queueDepth: 0,
  lastSeen: '2026-05-14T03:12:00Z',
};

describe('NodeCard', () => {
  it('renders node id, online badge, queue depth, gpu bar, and lastSeen', () => {
    render(<NodeCard node={onlineNode} />);

    expect(screen.getByText('lab02')).toBeInTheDocument();
    expect(screen.getByText('在线')).toBeInTheDocument();
    expect(screen.getByText('队列深度: 1')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { hidden: true })).toBeInTheDocument();
    expect(screen.getByText('NVIDIA A100 80GB')).toBeInTheDocument();
  });

  it('renders offline node without gpu bar and with muted styling', () => {
    const { container } = render(<NodeCard node={offlineNode} />);

    expect(screen.getByText('lab06')).toBeInTheDocument();
    expect(screen.getByText('离线')).toBeInTheDocument();
    expect(screen.getByText('队列深度: 0')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar', { hidden: true })).not.toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();

    // Card should have opacity-60 class
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('opacity-60');
  });

  it('shows lastSeen as locale time string', () => {
    render(<NodeCard node={onlineNode} />);
    // The exact format depends on locale, but the element should exist
    expect(screen.getByText(/最后在线:/)).toBeInTheDocument();
  });
});
