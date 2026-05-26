import type { ToolExecution } from '../types';

interface StatusBadgeProps {
  status: ToolExecution['status'];
}

const STATUS_CONFIG = {
  running: {
    bg: 'rgba(245, 158, 11, 0.2)',
    border: 'rgba(245, 158, 11, 0.4)',
    color: '#f59e0b',
    label: 'Running',
    dotAnimation: true
  },
  completed: {
    bg: 'rgba(16, 185, 129, 0.2)',
    border: 'rgba(16, 185, 129, 0.3)',
    color: '#10b981',
    label: 'Completed',
    dotAnimation: false
  },
  failed: {
    bg: 'rgba(239, 68, 68, 0.2)',
    border: 'rgba(239, 68, 68, 0.3)',
    color: '#ef4444',
    label: 'Failed',
    dotAnimation: false
  },
  pending: {
    bg: 'rgba(61, 74, 98, 0.3)',
    border: 'rgba(61, 74, 98, 0.5)',
    color: '#7a8aaa',
    label: 'Pending',
    dotAnimation: false
  }
} as const;

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: '3px 8px',
        background: config.bg,
        border: `1px solid ${config.border}`,
        borderRadius: '5px'
      }}
    >
      <div
        style={{
          width: '5px',
          height: '5px',
          borderRadius: '50%',
          background: config.color,
          boxShadow: `0 0 6px ${config.color}`,
          animation: config.dotAnimation ? 'mdpilot-status-pulse 2s ease-in-out infinite' : 'none'
        }}
      />
      <span
        style={{
          fontSize: '10px',
          color: config.color,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}
      >
        {config.label}
      </span>
    </div>
  );
}
