import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it } from 'vitest';

import { ApiError, toApiError } from './error';

function makeAxiosError(status: number, data: unknown): AxiosError {
  const err = new AxiosError('boom');
  err.response = {
    status,
    statusText: 'X',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data,
  };
  return err;
}

describe('toApiError', () => {
  it('wraps backend RFC7807 body', () => {
    const ax = makeAxiosError(409, {
      type: 'about:blank',
      title: 'Conflict',
      detail: 'task already running',
      code: 'TASK_RUNNING',
    });
    const err = toApiError(ax);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.code).toBe('TASK_RUNNING');
    expect(err.message).toBe('task already running');
  });

  it('falls back to status text when body lacks detail', () => {
    const ax = makeAxiosError(500, {});
    const err = toApiError(ax);
    expect(err.code).toBe('HTTP_500');
  expect(err.message).toMatch(/server error/i);
  });

  it('handles non-AxiosError as UNKNOWN', () => {
    const err = toApiError(new Error('boom'));
    expect(err.code).toBe('UNKNOWN');
    expect(err.status).toBe(0);
  });
});
