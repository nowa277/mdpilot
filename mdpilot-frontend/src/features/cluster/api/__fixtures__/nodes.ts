import type { NodeStatus } from '@shared/types';

export const mockNodes: NodeStatus[] = [
  { id: 'lab03', online: true, queueDepth: 0, lastSeen: '2026-05-14T10:00:00Z' },
  {
    id: 'lab02',
    online: true,
    gpu: { id: 'gpu-lab02-0', model: 'NVIDIA A100 80GB', usedMB: 6_400, totalMB: 81_920 },
    queueDepth: 1,
    lastSeen: '2026-05-14T10:00:00Z',
  },
  {
    id: 'lab06',
    online: false,
    gpu: { id: 'gpu-lab06-0', model: 'NVIDIA RTX 4090 24GB', usedMB: 0, totalMB: 24_564 },
    queueDepth: 0,
    lastSeen: '2026-05-14T03:12:00Z',
  },
];
