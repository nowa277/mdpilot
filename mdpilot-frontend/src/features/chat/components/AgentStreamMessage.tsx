import { memo, useMemo } from 'react';
import type { AgentBlock as AgentBlockType } from '@/shared/types/api.gen';
import { ThinkingBlock } from './ThinkingBlock';
import { ResponseContent } from './ResponseContent';
import { AgentBlock } from './AgentBlock';
import { ToolStatusBar } from './ToolStatusBar';
import { useWorkflowSync } from '@/features/workflow/hooks/useWorkflowSync';

interface AgentStreamMessageProps {
  blocks: AgentBlockType[];
  interrupted?: boolean;
}

export const AgentStreamMessage = memo(function AgentStreamMessage({
  blocks,
  interrupted,
}: AgentStreamMessageProps) {
  useWorkflowSync(blocks);

  const segments = useMemo(() => {
    const result: Array<
      | { kind: 'single'; block: AgentBlockType }
      | { kind: 'tools'; blocks: Extract<AgentBlockType, { type: 'tool_call' }>[] }
    > = [];

    let toolBuffer: Extract<AgentBlockType, { type: 'tool_call' }>[] = [];

    const flushTools = () => {
      if (toolBuffer.length > 0) {
        result.push({ kind: 'tools', blocks: [...toolBuffer] });
        toolBuffer = [];
      }
    };

    for (const block of blocks) {
      if (block.type === 'tool_call') {
        toolBuffer.push(block as Extract<AgentBlockType, { type: 'tool_call' }>);
      } else {
        flushTools();
        result.push({ kind: 'single', block });
      }
    }
    flushTools();
    return result;
  }, [blocks]);

  return (
    <div className="space-y-3">
      {segments.map((seg, i) => {
        if (seg.kind === 'tools') {
          return <ToolStatusBar key={`tools-${i}`} blocks={seg.blocks} />;
        }

        const block = seg.block;
        switch (block.type) {
          case 'thinking':
            return <ThinkingBlock key={`think-${i}`} reasoning={block.content} />;
          case 'response':
            return <ResponseContent key={`resp-${i}`} content={block.content} />;
          case 'streaming':
            return (
              <div key={`stream-${i}`} className="text-sm leading-relaxed whitespace-pre-wrap">
                {block.content}
              </div>
            );
          case 'error':
            return <AgentBlock key={`err-${i}`} block={block} />;
          default:
            return <AgentBlock key={`other-${i}`} block={block} />;
        }
      })}

      {interrupted && (
        <div className="text-xs text-[#3d4a62] italic mt-2">Response was interrupted</div>
      )}
    </div>
  );
});
