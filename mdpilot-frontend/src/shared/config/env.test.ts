import { afterEach, describe, expect, it, vi } from 'vitest';

import { readEnv } from './env';

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('readEnv', () => {
  it('parses mock mode with defaults', () => {
    vi.stubEnv('VITE_API_MODE', 'mock');
    vi.stubEnv('VITE_API_BASE', 'http://lab03:8000');
    vi.stubEnv('VITE_WS_BASE', 'ws://lab03:8000');
    vi.stubEnv('VITE_API_TOKEN', '');
    expect(readEnv()).toEqual({
      mode: 'mock',
      apiBase: 'http://lab03:8000',
      wsBase: 'ws://lab03:8000',
      apiToken: '',
    });
  });

  it('reads API token when configured', () => {
    vi.stubEnv('VITE_API_MODE', 'direct');
    vi.stubEnv('VITE_API_BASE', 'http://lab03:8000');
    vi.stubEnv('VITE_WS_BASE', 'ws://lab03:8000');
    vi.stubEnv('VITE_API_TOKEN', 'test-token');
    expect(readEnv().apiToken).toBe('test-token');
  });

  it('throws on unsupported mode', () => {
    vi.stubEnv('VITE_API_MODE', 'live');
    vi.stubEnv('VITE_API_BASE', 'http://lab03:8000');
    vi.stubEnv('VITE_WS_BASE', 'ws://lab03:8000');
    expect(() => readEnv()).toThrow(/VITE_API_MODE/);
  });

  it('throws when API base missing in direct mode', () => {
    vi.stubEnv('VITE_API_MODE', 'direct');
    vi.stubEnv('VITE_API_BASE', '');
    vi.stubEnv('VITE_WS_BASE', 'ws://lab03:8000');
    expect(() => readEnv()).toThrow(/VITE_API_BASE/);
  });
});
