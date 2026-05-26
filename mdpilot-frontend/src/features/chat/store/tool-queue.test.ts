import { describe, expect, it } from 'vitest';

import {
  addQueueItem,
  disableTool,
  getAvailableTools,
  removeQueueItem,
  reorderQueue,
  TOOL_MODULES,
} from './tool-queue';

describe('tool queue helpers', () => {
  it('adds enabled tools and prevents duplicates', () => {
    const queue = addQueueItem([], 'alphafold2_predict');
    expect(queue).toHaveLength(1);
    expect(addQueueItem(queue, 'alphafold2_predict')).toHaveLength(1);
  });

  it('removes queue items by id', () => {
    const queue = addQueueItem([], 'alphafold2_predict');
    expect(removeQueueItem(queue, queue[0].id)).toHaveLength(0);
  });

  it('reorders queue items', () => {
    const queue = addQueueItem(addQueueItem([], 'bioreason_annotate'), 'alphafold2_predict');
    const reordered = reorderQueue(queue, queue[0].id, queue[1].id, 'after');
    expect(reordered.map((item) => item.tool)).toEqual(['alphafold2_predict', 'bioreason_annotate']);
    expect(reordered.map((item) => item.order)).toEqual([1, 2]);
  });

  it('removes disabled tools from the queue and module pool', () => {
    const queue = addQueueItem([], 'bash_run');
    const modules = TOOL_MODULES.map((tool) => (tool.tool === 'bash_run' ? { ...tool, enabled: true } : tool));
    const result = disableTool(queue, modules, 'bash_run');
    expect(result.queue).toHaveLength(0);
    expect(result.modules.find((tool) => tool.tool === 'bash_run')?.enabled).toBe(false);
    expect(getAvailableTools(result.queue, result.modules).some((tool) => tool.tool === 'bash_run')).toBe(false);
  });
});
