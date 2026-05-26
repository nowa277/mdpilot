import { api } from './axios';

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'healthy';
  commit?: string;
  uptimeSec?: number;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const resp = await api().get<HealthResponse>('/health');
  return resp.data;
}
