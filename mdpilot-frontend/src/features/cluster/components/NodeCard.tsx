import { GpuMiniCard } from './GpuMiniCard';
import { calculateNodeStats } from '../utils/gpuUtils';
import type { NodeStatus } from '@/shared/types/api.gen';

interface NodeCardProps {
  node: NodeStatus;
  onExpand?: () => void;
}

export function NodeCard({ node, onExpand }: NodeCardProps) {
  const gpus = node.gpus || [];
  const stats = calculateNodeStats(gpus);

  return (
    <div
      className="glass-card p-5 cursor-pointer hover:-translate-y-0.5 transition-all light-sweep"
      onClick={onExpand}
    >
      <div className="flex justify-between items-center mb-4 pb-3 border-b border-border-1 relative z-10">
        <div className="text-xl font-semibold text-accent-1" style={{ textShadow: '0 0 20px rgba(0, 207, 170, 0.3)' }}>
          {node.id}
        </div>
        <div className={`px-3 py-1 rounded-md text-xs font-medium relative overflow-hidden ${
          node.online
            ? 'bg-state-success/20 text-state-success border border-state-success/30'
            : 'bg-border-1 text-text-3'
        }`}>
          {node.online && <span className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-state-success/20 to-transparent" />}
          <span className="relative z-10">{node.online ? 'ONLINE' : 'OFFLINE'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4 relative z-10">
        <div className="bg-black/30 p-2.5 rounded-lg border border-border-1">
          <div className="text-[11px] text-text-2 uppercase tracking-wide mb-1">Queue Depth</div>
          <div className="text-lg font-semibold text-text-1">{node.queueDepth}</div>
        </div>
        <div className="bg-black/30 p-2.5 rounded-lg border border-border-1">
          <div className="text-[11px] text-text-2 uppercase tracking-wide mb-1">Avg Temp</div>
          <div className="text-lg font-semibold text-text-1">{stats.avgTemperature}°C</div>
        </div>
      </div>

      {gpus.length > 0 && (
        <div className="grid grid-cols-4 gap-3 relative z-10">
          {gpus.map((gpu) => (
            <GpuMiniCard key={gpu.id} gpu={gpu} />
          ))}
        </div>
      )}

      <div className="text-center mt-3 text-xs text-text-2 opacity-70 hover:opacity-100 hover:text-accent-1 transition-all relative z-10">
        点击查看详细信息
      </div>
    </div>
  );
}
