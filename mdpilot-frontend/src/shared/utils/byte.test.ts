import { describe, expect, it } from 'vitest';

import { formatBytes } from './byte';

describe('formatBytes', () => {
  it.each([
    [0, '0 B'],
    [512, '512 B'],
    [1024, '1.0 KB'],
    [1536, '1.5 KB'],
    [1_048_576, '1.0 MB'],
    [5_242_880, '5.0 MB'],
    [1_073_741_824, '1.0 GB'],
  ])('formats %i as %s', (input, expected) => {
    expect(formatBytes(input)).toBe(expected);
  });

  it('rejects negative', () => {
    expect(formatBytes(-1)).toBe('0 B');
  });
});
