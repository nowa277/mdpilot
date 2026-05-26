import { describe, expect, it } from 'vitest';

import * as ChatExports from './index';

describe('Chat feature exports', () => {
  it('should export ChatList', () => {
    expect(ChatExports.ChatList).toBeDefined();
  });
});
