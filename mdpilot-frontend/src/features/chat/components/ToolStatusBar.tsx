import { memo } from 'react';
import type { AgentBlock } from '@/shared/types/api.gen';

interface ToolStatusBarProps {
  blocks: Extract<AgentBlock, { type: 'tool_call' }>[];
}

const STATUS_CONFIG = {
  completed: { icon: '✓', color: '#10b981', label: '' },
  running: { icon: '⟳', color: '#f59e0b', label: 'running...' },
  failed: { icon: '✗', color: '#ef4444', label: 'failed' },
  pending: { icon: '○', color: '#3d4a62', label: 'pending' },
} as const;

function getBorderStyle(blocks: ToolStatusBarProps['blocks']): React.CSSProperties['border'] {
  if (blocks.some((b) => b.status === 'failed')) return '1px solid rgba(239,68,68,0.3)';
  if (blocks.some((b) => b.status === 'running')) return '1px solid rgba(245,158,11,0.4)';
  return '1px solid rgba(16,185,129,0.3)';
}

function getBoxShadow(blocks: ToolStatusBarProps['blocks']): string {
  if (blocks.some((b) => b.status === 'failed')) return '0 0 15px rgba(239,68,68,0.1)';
  if (blocks.some((b) => b.status === 'running')) return '0 0 15px rgba(245,158,11,0.15)';
  return '0 0 12px rgba(16,185,129,0.08)';
}

export const ToolStatusBar = memo(function ToolStatusBar({ blocks }: ToolStatusBarProps) {
  if (blocks.length === 0) return null;

  return (
    <div
      style={{
        background: 'rgba(15,23,42,0.6)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: getBorderStyle(blocks),
        borderRadius: '8px',
        padding: '10px 14px',
        margin: '0 0 12px 0',
        boxShadow: getBoxShadow(blocks),
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {blocks.map((block) => {
          const config = STATUS_CONFIG[block.status] ?? STATUS_CONFIG.pending;
          return (
            <div
              key={block.tool_call_id ?? block.name}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}
            >
              <span
                style={{
                  color: config.color,
                  fontWeight: 700,
                  fontSize: '14px',
                  animation:
                    block.status === 'running'
                      ? 'mdpilot-tool-pulse 2s cubic-bezier(0.4,0,0.6,1) infinite'
                      : undefined,
                }}
              >
                {config.icon}
              </span>
              <span style={{ color: '#94A3B8' }}>{block.name}</span>
              <span style={{ color: '#3d4a62', fontSize: '11px', marginLeft: 'auto' }}>
                {config.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
});
