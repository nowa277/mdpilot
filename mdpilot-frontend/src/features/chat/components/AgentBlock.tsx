import type { AgentBlock as AgentBlockType } from '@shared/types';
import { cn } from '@shared/utils';
import { useState } from 'react';

import { MarkdownRenderer } from './MarkdownRenderer';

interface Props {
  block: AgentBlockType;
}

export function AgentBlock({ block }: Props) {
  const [open, setOpen] = useState(
    block.type === 'thinking' ||
      block.type === 'progress' ||
      block.type === 'error' ||
      block.type === 'response' ||
      block.type === 'tool_result' ||
      (block.type === 'tool_call' && block.status !== 'completed'),
  );

  const getBlockLabel = () => {
    switch (block.type) {
      case 'thinking':
        return 'Thinking';
      case 'tool_call':
        return `Tool: ${block.name}`;
    case 'tool_result':
        return `Result: ${block.name}`;
      case 'progress':
        return 'Progress';
      case 'error':
        return 'Error';
      case 'response':
        return 'Response';
    }
  };

  const getBlockContent = () => {
    switch (block.type) {
      case 'thinking':
        return block.content;
      case 'tool_call':
        if (block.error) return `Error: ${block.error}`;
        if (block.result) return block.result;
        if (block.input) return JSON.stringify(block.input, null, 2);
        return `Status: ${block.status}`;
      case 'tool_result':
        return block.result;
      case 'progress':
        return block.percent !== undefined
          ? `${block.message} (${block.percent}%)`
          : block.message;
      case 'error':
     return block.message;
      case 'response':
        return block.content;
      case 'streaming':
        return block.content;
      default:
        return '';
    }
  };

  const getBlockColor = () => {
    if (block.type === 'error') return 'text-red-600';
    if (block.type === 'tool_call' && block.status === 'failed') return 'text-red-600';
    if (block.type === 'progress') return 'text-blue-600';
    return 'text-text-3';
  };

  const content = getBlockContent();
  const isCollapsible = content.length > 0;

  return (
    <div className="mb-2 rounded-chip border border-border-1 bg-bg-2">
      <button
        type="button"
        onClick={() => isCollapsible && setOpen((v) => !v)}
        disabled={!isCollapsible}
        className={cn(
       'flex w-full items-center gap-2 px-3 py-2 text-xs font-medium transition-colors',
          getBlockColor(),
          isCollapsible && 'hover:text-text-2 cursor-pointer',
          !isCollapsible && 'cursor-default',
        )}
      >
        {isCollapsible && (
          <svg
        className={cn('h-3 w-3 transition-transform', open && 'rotate-90')}
            viewBox="0 0 12 12"
      fill="currentColor"
            aria-hidden="true"
          >
            <path d="M4 2l4 4-4 4" />
          </svg>
        )}
        {getBlockLabel()}
      </button>
      {open && isCollapsible && (
        <div className="border-t border-border-1 px-3 py-2 text-xs leading-relaxed text-text-3 max-h-[300px] overflow-y-auto">
          {block.type === 'response' ? (
            <MarkdownRenderer source={content} />
          ) : (
            <div className="whitespace-pre-wrap">{content}</div>
          )}
      </div>
      )}
    </div>
  );
}
