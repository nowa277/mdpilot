// src/shared/types/api.gen.test.ts
import { describe, expect,it } from 'vitest';

import type { AgentBlock } from './api.gen';

describe('AgentBlock types', () => {
  it('should allow tool_call with backend execution info', () => {
    const block: AgentBlock = {
   type: 'tool_call',
      name: 'alphafold2_predict',
    status: 'running',
      input: { sequence: 'MKTAYIAK' },
      backend: {
        node: 'lab02',
        gpuInfo: '9× TITAN V',
      },
    };

    expect(block.type).toBe('tool_call');
    expect(block.backend?.node).toBe('lab02');
  });

  it('should allow tool_call without backend info', () => {
    const block: AgentBlock = {
      type: 'tool_call',
      name: 'bash_run',
    status: 'completed',
      result: 'Success',
    };

    expect(block.type).toBe('tool_call');
    expect(block.backend).toBeUndefined();
  });
});
