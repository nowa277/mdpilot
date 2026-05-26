import { RingChart } from './RingChart';

interface Props {
  total: number;
  completed: number;
  running: number;
  failed: number;
}

export function WorkflowHeader({ total, completed, running, failed }: Props) {
  const pending = total - completed - running - failed;
  const stats = { total, completed, running, failed, pending };

  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '20px' }}>
      <RingChart stats={stats} />

      {/* Legend */}
      <div style={{ marginLeft: '24px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#10b981',
              boxShadow: '0 0 8px rgba(16, 185, 129, 0.6)'
            }}
          />
          <span style={{ fontSize: '12px', color: '#dde4f0' }}>
            Completed: <strong>{completed}</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#f59e0b',
              boxShadow: '0 0 8px rgba(245, 158, 11, 0.6)'
            }}
          />
          <span style={{ fontSize: '12px', color: '#dde4f0' }}>
            Running: <strong>{running}</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#ef4444',
              boxShadow: '0 0 8px rgba(239, 68, 68, 0.6)'
            }}
          />
          <span style={{ fontSize: '12px', color: '#dde4f0' }}>
            Failed: <strong>{failed}</strong>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#3d4a62'
            }}
          />
          <span style={{ fontSize: '12px', color: '#7a8aaa' }}>
            Pending: <strong>{pending}</strong>
          </span>
        </div>
      </div>
    </div>
  );
}
