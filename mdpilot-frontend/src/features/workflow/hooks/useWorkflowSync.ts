import type { AgentBlock } from '@shared/types';
import { useEffect, useRef } from 'react';

import { useWorkflowStore } from '../store/workflow.store';
import type { ToolExecution } from '../types';

/**
 * Syncs SSE agent blocks to the workflow store.
 * Filters tool_call blocks and updates store based on status changes.
 */
export function useWorkflowSync(blocks: AgentBlock[]) {
  const { addTool, updateToolStatus, completeTool, failTool, updateToolProgress } = useWorkflowStore();
  const processedToolsRef = useRef(new Map<string, string>());

  useEffect(() => {
    const toolBlocks = blocks.filter(
      (block): block is Extract<AgentBlock, { type: 'tool_call' }> =>
        block.type === 'tool_call',
    );

    toolBlocks.forEach((block) => {
      const rawId = (block as any).tool_call_id as string | undefined;
      let toolId: string;
      if (rawId) {
        toolId = rawId;
      } else {
        const inputStr = block.input ? JSON.stringify(block.input) : '';
        toolId = `${block.name}-${inputStr.slice(0, 50)}`;
      }
      const previousStatus = processedToolsRef.current.get(toolId);

      // New tool - add to store
      if (!previousStatus) {
        const tool: ToolExecution = {
          id: toolId,
          name: block.name,
          status: block.status,
          startTime: Date.now(),
          params: (block.input as Record<string, unknown>) || {},
        };

        if (block.backend) {
          tool.backend = {
            node: block.backend.node,
            resources: block.backend.gpuInfo || '',
          };
        }

        addTool(tool);
        processedToolsRef.current.set(toolId, block.status);
        return;
    }

      // Status changed - update store
      if (previousStatus !== block.status) {
        if (block.status === 'running') {
          updateToolStatus(toolId, 'running');
        } else if (block.status === 'completed') {
          // Calculate real duration
          const existing = useWorkflowStore.getState().tools.find((t) => t.id === toolId);
          const duration = existing ? Date.now() - existing.startTime : 0;
        const result = block.result ? { output: block.result } : {};
          completeTool(toolId, result, duration);
        } else if (block.status === 'failed') {
          failTool(toolId, block.error || 'Unknown error');
        }

    processedToolsRef.current.set(toolId, block.status);
      }
    });

    // Process progress blocks
    const progressBlocks = blocks.filter((b) => b.type === 'progress');
    progressBlocks.forEach((block) => {
      // Find current running tool
      const runningTools = useWorkflowStore.getState().tools.filter((t) => t.status === 'running');
      if (runningTools.length > 0) {
        const toolId = runningTools[runningTools.length - 1].id; // Latest running tool
        updateToolProgress(toolId, {
          percent: (block as any).percent ?? 0,
          stage: (block as any).message ?? '',
        eta: 0,
        });
      }
    });
  }, [blocks, addTool, updateToolStatus, completeTool, failTool, updateToolProgress]);
}
