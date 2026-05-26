import { GpuRing } from './GpuRing';
import { getGpuStatus, getMemoryPercent, getTemperatureColor } from '../utils/gpuUtils';
import type { GPUInfo } from '@/shared/types/api.gen';

interface GpuMiniCardProps {
  gpu: GPUInfo;
}

export function GpuMiniCard({ gpu }: GpuMiniCardProps) {
  const status = getGpuStatus(gpu);
  const memoryPercent = getMemoryPercent(gpu);
  const tempColor = getTemperatureColor(gpu.tempC || 0);

  const statusClass = status === 'warning' ? 'border-state-warning/40' : status === 'danger' ? 'border-state-error/40' : 'border-border-1';
  const statusAnim = status === 'warning' ? 'animate-pulse-warning' : status === 'danger' ? 'animate-pulse-danger' : '';

  return (
    <div
      className={`relative overflow-hidden rounded-lg bg-black/30 border p-3 transition-all duration-300 hover:scale-[1.03] hover:border-accent-1/30 ${statusClass} ${statusAnim}`}
    >
      <div className="relative z-10">
        <div className="text-[11px] text-text-2 mb-2">GPU {gpu.id}</div>

        <div className="flex justify-center mb-2">
          <GpuRing percent={memoryPercent} size="small" status={status} />
        </div>

        <div className="space-y-1 text-[11px] text-text-2 text-center">
          <div className="flex items-center justify-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm"
              style={{ background: 'linear-gradient(135deg, #00cfaa, #3b82f6)' }}
            />
            <span style={{ color: tempColor }}>{gpu.tempC ?? '--'}°C</span>
          </div>
          <div className="flex items-center justify-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm"
              style={{ background: 'linear-gradient(135deg, #8b5cf6, #ec4899)' }}
            />
            <span>{gpu.utilization ?? '--'}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
