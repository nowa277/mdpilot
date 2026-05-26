import type { ToolModuleConfig, ToolQueueItem } from '../types';

interface Props {
  queue: ToolQueueItem[];
  modules: ToolModuleConfig[];
}

export function AgentPlanFeedback({ queue, modules }: Props) {
  if (queue.length === 0) return null;
  const enabled = modules.filter((tool) => tool.enabled);
  const issues: string[] = [];
  const tools = queue.map((item) => item.tool);
  if (tools.includes('alphafold2_predict')) issues.push('AlphaFold2 需要 protein sequence');
  if (tools.includes('md_prep') && !tools.includes('alphafold2_predict')) issues.push('MD Prep 需要 PDB 输入');
  if (tools.includes('mmpbsa') && !tools.includes('amber_md')) issues.push('MMPBSA 需要 MD trajectory');

  return (
    <div className="agent-plan-feedback">
      <div className="agent-plan-feedback-title">Agent Plan Feedback</div>
      <p>
        当前启用工具队列：{queue.map((item) => item.label).join(' → ')}。
        {issues.length > 0 ? `需要确认：${issues.join('；')}。` : '依赖关系完整，可直接生成计划。'}
      </p>
      <div className="agent-plan-feedback-meta">
        enabled_tools: {enabled.length} · queue: {queue.length} · disabled: {modules.length - enabled.length}
      </div>
    </div>
  );
}
