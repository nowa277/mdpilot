import { ToolModuleManager, useChatUiStore } from '@features/chat';
import { WorkflowPanel } from '@features/workflow';
import { cn } from '@shared/utils';

interface RightPanelProps {
  width: number;
}

export function RightPanel({ width }: RightPanelProps) {
  const open = useChatUiStore((s) => s.rightPanelOpen);
  const activeTab = useChatUiStore((s) => s.rightPanelTab);
  const setTab = useChatUiStore((s) => s.setRightPanelTab);

  return (
    <aside
      className={cn(
        'flex h-full flex-col bg-bg-1/82 backdrop-blur-[24px] transition-[width] duration-200',
        open ? '' : 'w-0 overflow-hidden',
      )}
      style={{ width: open ? `${width}px` : '0' }}
    >
      <div className="right-panel-tabs">
        {(['workflow', 'tools'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setTab(tab)}
            className={cn('right-panel-tab', activeTab === tab && 'active')}
          >
            {tab === 'workflow' ? '工作流' : '工具'}
          </button>
        ))}
      </div>
      <div className="right-panel-body">
        {activeTab === 'workflow' && <WorkflowPanel />}
        {activeTab === 'tools' && <ToolModuleManager />}
      </div>
    </aside>
  );
}
