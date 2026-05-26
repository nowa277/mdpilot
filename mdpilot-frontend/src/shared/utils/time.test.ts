import { describe, expect, it } from 'vitest';

import { formatDuration, formatRelative } from './time';

describe('formatDuration', () => {
  it('renders sub-second as ms', () => {
    expect(formatDuration(450)).toBe('450ms');
  });
  it('renders seconds with one decimal', () => {
    expect(formatDuration(2400)).toBe('2.4s');
  });
  it('renders minutes + seconds', () => {
    expect(formatDuration(125_000)).toBe('2m05s');
  });
  it('renders hours + minutes', () => {
    expect(formatDuration(3_900_000)).toBe('1h05m');
  });
  it('rejects negative input by returning 0ms', () => {
    expect(formatDuration(-1)).toBe('0ms');
  });
});

describe('formatRelative', () => {
  const now = new Date('2026-05-14T12:00:00Z').getTime();
  it('returns 刚刚 within 30s', () => {
    expect(formatRelative(now - 10_000, now)).toBe('刚刚');
  });
  it('returns 分钟前', () => {
    expect(formatRelative(now - 5 * 60_000, now)).toBe('5 分钟前');
  });
  it('returns 小时前', () => {
    expect(formatRelative(now - 3 * 3_600_000, now)).toBe('3 小时前');
  });
  it('returns ISO date when older than 7 days', () => {
    expect(formatRelative(now - 10 * 86_400_000, now)).toBe('2026-05-04');
  });
});
