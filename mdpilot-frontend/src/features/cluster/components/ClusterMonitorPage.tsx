import { useState } from 'react';
import { NodeCard } from './NodeCard';
import { GpuDetailCard } from './GpuDetailCard';
import { useNodesQuery } from '../hooks/useNodes';
import '../styles/gpu-animations.css';

export function ClusterMonitorPage() {
  const { data: nodes, isLoading, isError, refetch } = useNodesQuery();
  const [expandedNodeId, setExpandedNodeId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-2">加载节点状态...</div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="text-state-error">无法获取节点状态</div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-accent-1/20 text-accent-1 rounded-lg hover:bg-accent-1/30 transition-colors"
        >
          重试
        </button>
      </div>
    );
  }

  const expandedNode = nodes?.find(n => n.id === expandedNodeId);

  return (
    <div className="h-full overflow-auto p-6">
      <div className="mb-8 text-center animate-fade-in-down">
        <h1 className="text-3xl font-semibold bg-gradient-to-r from-accent-1 to-accent-2 bg-clip-text text-transparent mb-2">
          集群监控
        </h1>
        <div className="text-sm text-text-2">每 30 秒缓存</div>
      </div>

      {expandedNodeId && (
        <div className="flex justify-center gap-3 mb-6 animate-fade-in">
          <button
            onClick={() => setExpandedNodeId(null)}
            className="px-6 py-2.5 rounded-lg glass-button text-text-2 hover:text-accent-1 transition-colors"
          >
            紧凑视图
          </button>
          <button className="px-6 py-2.5 rounded-lg bg-accent-1/20 text-accent-1 border border-accent-1/40">
            详细视图
          </button>
        </div>
      )}

      {!expandedNodeId && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 animate-fade-in-up">
          {nodes?.map((node) => (
            <NodeCard
              key={node.id}
              node={node}
              onExpand={() => setExpandedNodeId(node.id)}
            />
          ))}
        </div>
      )}

      {expandedNodeId && expandedNode && (
        <div className="max-w-4xl mx-auto animate-fade-in-up">
          <h2 className="text-2xl font-semibold text-accent-1 mb-6">
            {expandedNode.id} - 详细GPU信息
          </h2>
          <div className="space-y-4">
            {(expandedNode.gpus || []).map((gpu) => (
              <GpuDetailCard key={gpu.id} gpu={gpu} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
