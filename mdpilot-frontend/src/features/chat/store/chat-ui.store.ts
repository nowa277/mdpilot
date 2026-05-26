import type { ToolModuleConfig, ToolQueueItem } from '@features/chat/types';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { TOOL_MODULES } from './tool-queue';

export type RightPanelTab = 'workflow' | 'tools';

interface ChatUiState {
  rightPanelOpen: boolean;
  toggleRightPanel(): void;
  setRightPanel(open: boolean): void;
  rightPanelTab: RightPanelTab;
  setRightPanelTab(tab: RightPanelTab): void;
  toolModules: ToolModuleConfig[];
  setToolModules(modules: ToolModuleConfig[]): void;
  toggleToolModule(toolName: string): void;
  toolQueue: ToolQueueItem[];
  setToolQueue(queue: ToolQueueItem[]): void;
}

export const useChatUiStore = create<ChatUiState>()(
  persist(
    (set) => ({
      rightPanelOpen: true,
      toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
    setRightPanel: (open) => set({ rightPanelOpen: open }),
      rightPanelTab: 'workflow',
      setRightPanelTab: (tab) => set({ rightPanelTab: tab }),
      toolModules: TOOL_MODULES,
      setToolModules: (modules) => set({ toolModules: modules }),
      toggleToolModule: (toolName) =>
        set((s) => ({
          toolModules: s.toolModules.map((m) =>
            m.tool === toolName ? { ...m, enabled: !m.enabled } : m,
          ),
          toolQueue: s.toolModules.find((m) => m.tool === toolName)?.enabled
            ? s.toolQueue.filter((item) => item.tool !== toolName)
            : s.toolQueue,
        })),
      toolQueue: [],
      setToolQueue: (queue) => set({ toolQueue: queue }),
    }),
    {
      name: 'mdpilot.chat-ui',
      partialize: (s) => ({
        rightPanelOpen: s.rightPanelOpen,
        rightPanelTab: s.rightPanelTab,
        toolModules: s.toolModules,
        toolQueue: s.toolQueue,
      }),
    },
  ),
);
