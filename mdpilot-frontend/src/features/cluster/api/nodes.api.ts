import { api } from '@shared/api';

import type { NodeStatus } from '../types';

export async function listNodes(): Promise<NodeStatus[]> {
  const resp = await api().get<NodeStatus[]>('/api/nodes');
  return resp.data;
}
