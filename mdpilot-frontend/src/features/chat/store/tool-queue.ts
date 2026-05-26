import type { ToolModuleConfig, ToolQueueItem } from '@features/chat/types';

export const TOOL_MODULES: ToolModuleConfig[] = [
  {
    id: 'tool-bioreason',
    tool: 'bioreason_annotate',
    label: 'Bioreason Annotate',
    description: '蛋白功能注释',
    route: 'lab06',
    tags: ['lab06', 'ready', 'GO'],
    enabled: true,
  },
  {
    id: 'tool-alphafold2',
    tool: 'alphafold2_predict',
    label: 'AlphaFold2 Predict',
    description: '蛋白三维结构预测',
    route: 'lab02',
    tags: ['lab02', 'ready', 'full_dbs'],
    enabled: true,
  },
  {
    id: 'tool-mdprep',
    tool: 'md_prep',
    label: 'System Prepare',
    description: 'AMBER 体系构建及参数化准备',
    route: 'lab03',
    tags: ['depends:PDB', 'optional'],
    enabled: true,
  },
  {
    id: 'tool-ambermd',
    tool: 'amber_md',
    label: 'AMBER MD',
    description: 'Amber 生产模拟',
    route: 'lab03',
    tags: ['GPU', 'optional', 'pmemd.cuda'],
    enabled: true,
  },
  {
    id: 'tool-mmpbsa',
    tool: 'mmpbsa',
    label: 'MMPBSA',
    description: '结合自由能分析',
  route: 'lab03',
    tags: ['analysis', 'optional'],
    enabled: true,
  },
  {
    id: 'tool-vmd',
    tool: 'vmd_render',
    label: 'VMD Render',
    description: '轨迹可视化与报告图生成',
    route: 'local',
    tags: ['render', 'optional'],
    enabled: true,
  },
  {
    id: 'tool-pymol',
    tool: 'pymol_render',
    label: 'PyMOL Render',
    description: '3D 结构可视化与渲染生成',
    route: 'local',
    tags: ['render', 'optional'],
    enabled: true,
  },
  {
    id: 'tool-bash',
    tool: 'bash_run',
    label: 'Bash Run',
    description: 'shell 命令执行',
    route: 'lab03',
    tags: ['restricted', 'manual'],
    enabled: false,
  },
  {
    id: 'tool-knowledge',
    tool: 'knowledge_search',
    label: 'Knowledge Search',
    description: '检索项目知识库与参考资料。',
    route: 'lab03',
    tags: ['lab03 base', 'ready'],
    enabled: true,
  },
];

function normalizeOrder(queue: ToolQueueItem[]): ToolQueueItem[] {
  return queue.map((item, index) => ({ ...item, order: index + 1 }));
}
export function addQueueItem(queue: ToolQueueItem[], toolName: string): ToolQueueItem[] {
  if (queue.some((item) => item.tool === toolName)) return queue;
  const tool = TOOL_MODULES.find((item) => item.tool === toolName);
  if (!tool || !tool.enabled) return queue;
  const newItem: ToolQueueItem = {
    id: `queue-${toolName}-${crypto.randomUUID()}`,
    tool: tool.tool,
    order: queue.length + 1,
    label: tool.label,
  };
  if (tool.defaults) {
    newItem.constraints = tool.defaults;
  }
  return normalizeOrder([...queue, newItem]);
}

export function removeQueueItem(queue: ToolQueueItem[], queueId: string): ToolQueueItem[] {
  return normalizeOrder(queue.filter((item) => item.id !== queueId));
}

export function reorderQueue(
  queue: ToolQueueItem[],
  draggedId: string,
  targetId: string,
  position: 'before' | 'after',
): ToolQueueItem[] {
  if (draggedId === targetId) return queue;
  const dragged = queue.find((item) => item.id === draggedId);
  if (!dragged) return queue;
  const withoutDragged = queue.filter((item) => item.id !== draggedId);
  const targetIndex = withoutDragged.findIndex((item) => item.id === targetId);
  if (targetIndex === -1) return queue;
  const insertIndex = position === 'after' ? targetIndex + 1 : targetIndex;
  return normalizeOrder([
    ...withoutDragged.slice(0, insertIndex),
    dragged,
    ...withoutDragged.slice(insertIndex),
  ]);
}

export function disableTool(
  queue: ToolQueueItem[],
  modules: ToolModuleConfig[],
  toolName: string,
): { queue: ToolQueueItem[]; modules: ToolModuleConfig[] } {
  return {
    queue: normalizeOrder(queue.filter((item) => item.tool !== toolName)),
    modules: modules.map((item) => (item.tool === toolName ? { ...item, enabled: false } : item)),
  };
}

export function getAvailableTools(
  queue: ToolQueueItem[],
  modules: ToolModuleConfig[],
): ToolModuleConfig[] {
  const queued = new Set(queue.map((item) => item.tool));
  return modules.filter((tool) => tool.enabled && !queued.has(tool.tool));
}
