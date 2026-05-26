import { useWorkflowStore } from '../store/workflow.store';
import type { WorkflowStatistics } from '../types';
import { EmptyState } from './EmptyState';
import { ToolCardList } from './ToolCardList';
import { WorkflowHeader } from './WorkflowHeader';

function calculateStatistics(tools: ReturnType<typeof useWorkflowStore.getState>['tools']): WorkflowStatistics {
  return {
    total: tools.length,
    completed: tools.filter((t) => t.status === 'completed').length,
    running: tools.filter((t) => t.status === 'running').length,
    failed: tools.filter((t) => t.status === 'failed').length,
    pending: tools.filter((t) => t.status === 'pending').length,
  };
}

export function WorkflowPanel() {
  const tools = useWorkflowStore((state) => state.tools);
  const stats = calculateStatistics(tools);

  return (
    <div className="flex h-full flex-col">
      <WorkflowHeader
        total={stats.total}
        completed={stats.completed}
        running={stats.running}
        failed={stats.failed}
   />
      <div className="flex-1 overflow-y-auto">
    {tools.length === 0 ? <EmptyState /> : <ToolCardList tools={tools} />}
      </div>
    </div>
  );
}
