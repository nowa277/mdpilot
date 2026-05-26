import { useState, useEffect, useCallback } from 'react';
import { Outlet } from 'react-router-dom';
import { ResizableHandle } from '@shared/ui';
import { RightPanel } from './RightPanel';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 320;
const SIDEBAR_DEFAULT = 220;
const SIDEBAR_STORAGE_KEY = 'mdpilot.sidebar-width';

const RIGHT_PANEL_MIN = 280;
const RIGHT_PANEL_MAX = 450;
const RIGHT_PANEL_DEFAULT = 300;
const RIGHT_PANEL_STORAGE_KEY = 'mdpilot.right-panel-width';

export function WorkspaceLayout() {
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    return stored ? parseInt(stored, 10) : SIDEBAR_DEFAULT;
  });

  const [rightPanelWidth, setRightPanelWidth] = useState(() => {
    const stored = localStorage.getItem(RIGHT_PANEL_STORAGE_KEY);
    return stored ? parseInt(stored, 10) : RIGHT_PANEL_DEFAULT;
  });

  const handleSidebarResize = useCallback((delta: number) => {
    setSidebarWidth((prev) => {
      const newWidth = prev + delta;
      if (newWidth < SIDEBAR_MIN) return SIDEBAR_MIN;
      if (newWidth > SIDEBAR_MAX) return SIDEBAR_MAX;
      return newWidth;
    });
  }, []);

  const handleRightPanelResize = useCallback((delta: number) => {
    setRightPanelWidth((prev) => {
      const newWidth = prev - delta; // Subtract because dragging right decreases width
      if (newWidth < RIGHT_PANEL_MIN) return RIGHT_PANEL_MIN;
      if (newWidth > RIGHT_PANEL_MAX) return RIGHT_PANEL_MAX;
      return newWidth;
    });
  }, []);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, sidebarWidth.toString());
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [sidebarWidth]);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      localStorage.setItem(RIGHT_PANEL_STORAGE_KEY, rightPanelWidth.toString());
    }, 300);
    return () => clearTimeout(timeoutId);
  }, [rightPanelWidth]);

  return (
    <div className="workspace-shell">
      <Sidebar width={sidebarWidth} />
      <ResizableHandle
        onResize={handleSidebarResize}
        currentWidth={sidebarWidth}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
      <ResizableHandle
        onResize={handleRightPanelResize}
        currentWidth={rightPanelWidth}
      />
      <RightPanel width={rightPanelWidth} />
    </div>
  );
}
