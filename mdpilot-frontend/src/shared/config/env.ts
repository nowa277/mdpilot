export type ApiMode = 'mock' | 'proxy' | 'direct';

export interface AppEnv {
  mode: ApiMode;
  apiBase: string;
  wsBase: string;
  apiToken: string;
}

const VALID_MODES: readonly ApiMode[] = ['mock', 'proxy', 'direct'];

export function readEnv(): AppEnv {
  const mode = import.meta.env.VITE_API_MODE;
  if (!VALID_MODES.includes(mode as ApiMode)) {
    throw new Error(`VITE_API_MODE must be one of ${VALID_MODES.join('|')}; got ${String(mode)}`);
  }
  const apiBase = String(import.meta.env.VITE_API_BASE ?? '');
  const wsBase = String(import.meta.env.VITE_WS_BASE ?? '');
  const apiToken = String(import.meta.env.VITE_API_TOKEN ?? '');
  if (mode !== 'mock' && !apiBase) {
    throw new Error('VITE_API_BASE is required in proxy/direct mode');
  }
  return { mode: mode as ApiMode, apiBase, wsBase, apiToken };
}
