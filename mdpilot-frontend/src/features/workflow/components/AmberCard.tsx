import { useEffect, useState } from 'react';
import type { ToolCardProps } from '../types';
import { StatusBadge } from './StatusBadge';

function formatDuration(ms: number): string {
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

const STATUS_STYLES = {
  running: {
    border: '1px solid rgba(245, 158, 11, 0.4)',
    boxShadow: '0 0 24px rgba(245, 158, 11, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
    animation: 'mdpilot-card-glow 2.5s ease-in-out infinite'
  },
  completed: {
    border: '1px solid rgba(16, 185, 129, 0.3)',
    boxShadow: '0 0 16px rgba(16, 185, 129, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
    animation: 'none'
  },
  failed: {
    border: '1px solid rgba(239, 68, 68, 0.3)',
    boxShadow: '0 0 16px rgba(239, 68, 68, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
    animation: 'none'
  },
  pending: {
    border: '1px solid rgba(148, 163, 184, 0.1)',
    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
    animation: 'none'
  }
} as const;

export function AmberCard({ tool }: ToolCardProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (tool.status !== 'running') {
      setElapsed(0);
      return;
    }

    const startTime = tool.startTime;
    const interval = setInterval(() => {
      setElapsed(Date.now() - startTime);
    }, 1000);

    return () => clearInterval(interval);
  }, [tool.status, tool.startTime]);

  const statusStyle = STATUS_STYLES[tool.status];

  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.6)',
        backdropFilter: 'blur(20px)',
        borderRadius: '12px',
        padding: '14px',
        ...statusStyle,
        opacity: tool.status === 'pending' ? 0.7 : 1
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <div style={{ fontSize: '13px', fontWeight: 600, color: '#dde4f0' }}>
          💠 {tool.name}
        </div>
        <StatusBadge status={tool.status} />
      </div>

      {tool.backend && (
        <div style={{ fontSize: '11px', color: '#7a8aaa', marginBottom: '10px' }}>
          {tool.backend.node} • {tool.backend.resources}
        </div>
      )}

      {tool.status === 'running' && tool.progress && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
            <span style={{ fontSize: '10px', color: '#7a8aaa' }}>{tool.progress.stage}</span>
            <span style={{ fontSize: '10px', color: '#f59e0b', fontWeight: 600 }}>{tool.progress.percent}%</span>
          </div>
          <div style={{ height: '4px', background: 'rgba(15, 23, 42, 0.8)', borderRadius: '2px', overflow: 'hidden', border: '1px solid rgba(148, 163, 184, 0.1)' }}>
            <div style={{ width: `${tool.progress.percent}%`, height: '100%', background: 'linear-gradient(90deg, #f59e0b, #fbbf24)', boxShadow: '0 0 8px rgba(245, 158, 11, 0.6)' }} />
          </div>
        </div>
      )}

      {tool.status === 'failed' && tool.error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', borderLeft: '2px solid #ef4444', borderRadius: '4px', padding: '8px', marginBottom: '10px' }}>
          <div style={{ fontSize: '10px', color: '#f87171', lineHeight: 1.4 }}>{tool.error}</div>
        </div>
      )}

      <div style={{ fontSize: '10px', color: '#7a8aaa' }}>
        {tool.status === 'running' && (
          <>⏱ {formatDuration(elapsed)} elapsed{tool.progress?.eta ? ` • ETA: ${formatDuration(tool.progress.eta)}` : ''}</>
        )}
        {tool.status === 'completed' && tool.duration !== undefined && (
          <>⏱ Duration: {formatDuration(tool.duration)}</>
        )}
        {tool.status === 'failed' && tool.duration !== undefined && (
          <>⏱ Failed after: {formatDuration(tool.duration)}</>
        )}
        {tool.status === 'pending' && <>⏳ Waiting to start...</>}
      </div>
    </div>
  );
}
