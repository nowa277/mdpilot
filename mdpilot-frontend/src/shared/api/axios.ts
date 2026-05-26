import { readEnv } from '@shared/config';
import axios, { type AxiosInstance } from 'axios';

import { toApiError } from './error';

export function createApiClient(): AxiosInstance {
  const env = readEnv();
  const baseURL = env.mode === 'mock' ? '' : env.apiBase;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (env.apiToken) headers.Authorization = `Bearer ${env.apiToken}`;
  const instance = axios.create({
    baseURL,
    timeout: 15_000,
    headers,
  });
  instance.interceptors.response.use(
    (resp) => resp,
    (err: unknown) => Promise.reject(toApiError(err)),
  );
  return instance;
}
let cached: AxiosInstance | null = null;
export function api(): AxiosInstance {
  if (!cached) cached = createApiClient();
  return cached;
}
