import { readEnv } from '@shared/config';

/**
 * Build a WebSocket URL for the given path, using the configured `VITE_WS_BASE`
 * when present, otherwise deriving the base from `window.location`.
 *
 * @param path - WebSocket path beginning with `/` (e.g. `/ws/task/abc`).
 */
export function wsUrl(path: string): string {
  const env = readEnv();
  const base =
    env.wsBase ||
    (typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
      : '');
  const url = `${base}${path}`;
  if (env.apiToken) {
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}token=${encodeURIComponent(env.apiToken)}`;
  }
  return url;
}
