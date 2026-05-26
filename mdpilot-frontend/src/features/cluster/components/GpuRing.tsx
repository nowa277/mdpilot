interface GpuRingProps {
  percent: number;
  size: 'small' | 'large';
  status: 'normal' | 'warning' | 'danger';
  label?: string;
}

const SIZE_CONFIG = {
  small: { width: 60, radius: 24, strokeWidth: 6 },
  large: { width: 120, radius: 50, strokeWidth: 10 },
} as const;

const STATUS_COLORS = {
  normal: { stroke: '#00cfaa', glow: 'rgba(0, 207, 170, 0.6)' },
  warning: { stroke: '#f59e0b', glow: 'rgba(245, 158, 11, 0.6)' },
  danger: { stroke: '#ef4444', glow: 'rgba(239, 68, 68, 0.6)' },
} as const;

export function GpuRing({ percent, size, status, label }: GpuRingProps) {
  const config = SIZE_CONFIG[size];
  const circumference = 2 * Math.PI * config.radius;
  const strokeDashoffset = circumference * (1 - percent / 100);
  const colors = STATUS_COLORS[status];
  const center = config.width / 2;

  return (
    <div className="relative" style={{ width: config.width, height: config.width }}>
      <svg
        width={config.width}
        height={config.width}
        style={{ transform: 'rotate(-90deg)' }}
      >
        <circle
          cx={center}
          cy={center}
          r={config.radius}
          fill="none"
          stroke="rgba(148, 163, 184, 0.2)"
          strokeWidth={config.strokeWidth}
        />
        <circle
          cx={center}
          cy={center}
          r={config.radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={config.strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{
            transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
            filter: `drop-shadow(0 0 4px ${colors.glow})`,
          }}
        />
      </svg>

      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-center">
        <div
          className={`font-bold text-text-1 ${
            size === 'small' ? 'text-sm' : 'text-2xl'
          }`}
          style={{
            textShadow: `0 0 10px ${colors.glow}`,
          }}
        >
          {percent}%
        </div>
        {label && (
          <div className="text-[10px] text-text-2 uppercase tracking-wide">
            {label}
          </div>
        )}
      </div>
    </div>
  );
}
