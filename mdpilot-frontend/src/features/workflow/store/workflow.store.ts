import { create } from 'zustand';

import type { ToolExecution } from '../types';

interface WorkflowState {
  activeChatId: string | null;
  toolsMap: Record<string, ToolExecution[]>;
  tools: ToolExecution[];
  setActiveChat: (chatId: string | null) => void;
  addTool: (tool: ToolExecution) => void;
  updateToolStatus: (
    id: string,
    status: 'pending' | 'running' | 'completed' | 'failed',
  ) => void;
  updateToolProgress: (
    id: string,
    progress: { percent: number; stage: string; eta: number },
  ) => void;
  completeTool: (
    id: string,
    result: Record<string, unknown>,
    duration: number,
    outputFiles?: string[]  ,
  ) => void;
  failTool: (id: string, error: string) => void;
  clearTools: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  activeChatId: null,
  toolsMap: {},
  tools: [],

  setActiveChat: (chatId) =>
    set({
      activeChatId: chatId,
      tools: chatId ? (get().toolsMap[chatId] ?? []) : [],
    }),

  addTool: (tool) =>
    set((s) => {
      const chatId = s.activeChatId;
      if (!chatId) return s;
      const existing = s.toolsMap[chatId] ?? [];
      if (existing.some((t) => t.id === tool.id)) return s;
      const updated = [...existing, tool];
      return { toolsMap: { ...s.toolsMap, [chatId]: updated }, tools: updated };
    }),

  updateToolStatus: (id, status) =>
    set((s) => {
   const chatId = s.activeChatId;
    if (!chatId) return s;
      const updated = (s.toolsMap[chatId] ?? []).map((t) =>
     t.id === id ? { ...t, status } : t,
      );
      return { toolsMap: { ...s.toolsMap, [chatId]: updated }, tools: updated };
    }),

  updateToolProgress: (id, progress) =>
    set((s) => {
      const chatId = s.activeChatId;
      if (!chatId) return s;
      const updated = (s.toolsMap[chatId] ?? []).map((t) =>
        t.id === id ? { ...t, progress } : t,
      );
      return { toolsMap: { ...s.toolsMap, [chatId]: updated }, tools: updated };
    }),

  completeTool: (id, result, duration, outputFiles) =>
    set((s) => {
      const chatId = s.activeChatId;
      if (!chatId) return s;
      const updated = (s.toolsMap[chatId] ?? []).map((t) =>
        t.id === id
          ? {
            ...t,
        status: 'completed' as const,
              result,
           duration,
          endTime: Date.now(),
            ...(outputFiles ? { outputFiles } : {}),
            }
          : t,
      );
      return { toolsMap: { ...s.toolsMap, [chatId]: updated }, tools: updated };
    }),

  failTool: (id, error) =>
    set((s) => {
      const chatId = s.activeChatId;
      if (!chatId) return s;
      const updated = (s.toolsMap[chatId] ?? []).map((t) =>
        t.id === id
          ? {
              ...t,
            status: 'failed' as const,
              error,
              endTime: Date.now(),
            }
        : t,
      );
      return { toolsMap: { ...s.toolsMap, [chatId]: updated }, tools: updated };
    }),

  clearTools: () =>
    set((s) => {
      const chatId = s.activeChatId;
      if (!chatId) return { tools: [] };
   return { toolsMap: { ...s.toolsMap, [chatId]: [] }, tools: [] };
    }),
}));
