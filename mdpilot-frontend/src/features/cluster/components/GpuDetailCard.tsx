import { GpuRing } from './GpuRing';
import { getGpuStatus, getMemoryPercent, getTemperatureColor, formatMemoryGB } from '../utils/gpuUtils';
import type { GPUInfo } from '@/shared/types/api.gen';

interface GpuDetailCardProps {
  gpu: GPUInfo;
}

export function GpuDetailCard({ gpu }: GpuDetailCardProps) {
  const status = getGpuStatus(gpu);
  const memoryPercent = getMemoryPercent(gpu);
  const tempColor = getTemperatureColor(gpu.tempC || 0);

  const borderClass = status === 'warning' ? 'border-state-warning/40' : status === 'danger' ? 'border-state-error/40' : '';
  const animClass = status === 'warning' ? 'animate-pulse-warning' : status === 'danger' ? 'animate-pulse-danger' : '';

  return (
    <div
      className={`glass-card p-5 mb-4 relative overflow-hidden ${borderClass} ${animClass}`}
    >
      <div className="relative z-10">
        <div className="mb-4">
          <div className="text-base font-semibold text-text-1">
            GPU {gpu.id}: {gpu.model}
          </div>
        </div>

        <div className="grid grid-cols-[120px_1fr] gap-5 items-center">
          <div className="flex justify-center">
            <GpuRing percent={memoryPercent} size="large" status={status} label="Memory" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <MetricItem
              iconBg="linear-gradient(180deg, #00cfaa, #3b82f6)"
              label="Temperature"
              value={`${gpu.tempC ?? '--'}°C`}
              valueColor={tempColor}
            />
            <MetricItem
              iconBg="linear-gradient(180deg, #8b5cf6, #ec4899)"
              label="GPU Utilization"
              value={`${gpu.utilization ?? '--'}%`}
            />
            <MetricItem
              iconBg="linear-gradient(180deg, #f59e0b, #ef4444)"
              label="Power Draw"
              value={`${gpu.powerDraw ?? '--'}W / ${gpu.powerLimit ?? '--'}W`}
            />
            <MetricItem
              iconBg="linear-gradient(180deg, #3b82f6, #00cfaa)"
              label="Memory Used"
              value={`${formatMemoryGB(gpu.usedMB)} / ${formatMemoryGB(gpu.totalMB)} GB`}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricItem({ iconBg, label, value, valueColor }: {
  iconBg: string;
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="bg-black/30 p-3 rounded-lg border border-border-1 transition-colors hover:border-accent-1/30">
      <div className="flex items-center gap-2 text-[11px] text-text-2 mb-2">
        <span
          className="inline-block w-0.5 h-3 rounded"
          style={{ background: iconBg }}
        />
        {label}
      </div>
      <div className="text-base font-semibold text-text-1" style={valueColor ? { color: valueColor } : undefined}>
        {value}
      </div>
    </div>
  );
}
