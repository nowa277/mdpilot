import { useChatUiStore } from '@features/chat';
import { IconButton } from '@shared/ui';

export function Topbar() {
  const rightPanelOpen = useChatUiStore((s) => s.rightPanelOpen);

  return (
    <header className="glass-panel flex h-14 items-center justify-between border-b px-4">
      <div className="flex items-center gap-4">
        {/* Breadcrumb Navigation */}
        <div className="flex items-center gap-1.5 font-mono text-sm">
          <span className="text-text-3">/</span>
          <span className="font-medium text-text-1">workspace</span>
        </div>
      </div>

      {/* Right Panel Toggle */}
      <IconButton
        aria-label={rightPanelOpen ? 'Collapse right panel' : 'Expand right panel'}
        onClick={() => useChatUiStore.getState().toggleRightPanel()}
        className="glass-button"
      >
        {rightPanelOpen ? '›' : '‹'}
      </IconButton>
    </header>
  );
}
