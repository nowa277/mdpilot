import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { ensureUserId, USER_ID_KEY } from './user-id';

beforeEach(() => {
  localStorage.clear();
});
afterEach(() => {
  localStorage.clear();
});

describe('ensureUserId', () => {
  it('generates a stable id and stores it in localStorage', () => {
    const id1 = ensureUserId();
    expect(id1).toMatch(/^u-[a-z0-9-]{8,}$/);
    expect(localStorage.getItem(USER_ID_KEY)).toBe(id1);
    const id2 = ensureUserId();
    expect(id2).toBe(id1);
  });

  it('regenerates if stored value is invalid', () => {
    localStorage.setItem(USER_ID_KEY, 'garbage value not matching');
    const id = ensureUserId();
    expect(id).not.toBe('garbage value not matching');
    expect(localStorage.getItem(USER_ID_KEY)).toBe(id);
  });
});
