import type { ToolExecution } from '../types';
import { ToolCard } from './ToolCard';

interface ToolCardListProps {
  tools: ToolExecution[];
}

export function ToolCardList({ tools }: ToolCardListProps) {
  if (tools.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-500">
        No tools to display
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tools.map((tool) => (
    <div key={tool.id} data-testid="tool-card">
          <ToolCard tool={tool} />
        </div>
      ))}
    </div>
  );
}
