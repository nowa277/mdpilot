import { cn } from '@shared/utils';

const GPU_WARN_PCT = 80;
const GPU_DANGER_PCT = 95;

interface GpuUsageBarProps {
  usedMB: number;
  totalMB: number;
}

export function GpuUsageBar({ usedMB, totalMB }: GpuUsageBarProps) {
  const percent = totalMB > 0 ? Math.round((usedMB / totalMB) * 100) : 0;
  const clamped = Math.min(100, Math.max(0, percent));

  const barColor =
    clamped >= GPU_DANGER_PCT
      ? 'bg-danger'
      : clamped >= GPU_WARN_PCT
        ? 'bg-warning'
        : 'bg-accent-1';

  const usedGB = (usedMB / 1024).toFixed(1);
  const totalGB = (totalMB / 1024).toFixed(1);

  return (
    <div className="space-y-1">
      <div
        role="progressbar"
        aria-valuenow={usedMB}
        aria-valuemin={0}
        aria-valuemax={totalMB}
        aria-valuetext={`${usedGB} GB / ${totalGB} GB (${clamped}%)`}
        aria-label="GPU 显存"
        className="h-2 w-full overflow-hidden rounded-full bg-bg-2"
      >
        <div
          className={cn('h-full rounded-full transition-all duration-300', barColor)}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <p className="text-xs text-text-3">
        {usedGB} GB / {totalGB} GB ({clamped}%)
      </p>
    </div>
  );
}
