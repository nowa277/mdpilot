import type { WorkflowStatistics } from '../types';

interface RingChartProps {
  stats: WorkflowStatistics;
}

const RADIUS = 60;
const STROKE_WIDTH = 12;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function calculateSegments(stats: WorkflowStatistics) {
  const { total, completed, running, failed, pending } = stats;
  if (total === 0) return [];

  const segments = [];
  let offset = 0;

  if (completed > 0) {
    const length = (completed / total) * CIRCUMFERENCE;
    segments.push({
      color: '#10b981',
      length,
      offset,
      glow: 'drop-shadow(0 0 8px rgba(16, 185, 129, 0.6))'
    });
    offset += length;
  }

  if (running > 0) {
    const length = (running / total) * CIRCUMFERENCE;
    segments.push({
      color: '#f59e0b',
      length,
      offset,
      glow: 'drop-shadow(0 0 8px rgba(245, 158, 11, 0.6))'
    });
    offset += length;
  }

  if (failed > 0) {
    const length = (failed / total) * CIRCUMFERENCE;
    segments.push({
      color: '#ef4444',
      length,
      offset,
      glow: 'drop-shadow(0 0 8px rgba(239, 68, 68, 0.6))'
    });
    offset += length;
  }

  if (pending > 0) {
    const length = (pending / total) * CIRCUMFERENCE;
    segments.push({
      color: '#3d4a62',
      length,
      offset,
      glow: 'none'
    });
  }

  return segments;
}

export function RingChart({ stats }: RingChartProps) {
  const segments = calculateSegments(stats);

  return (
    <div style={{ position: 'relative', width: '160px', height: '160px', padding: '10px' }}>
      <svg
        width="160"
        height="160"
        style={{
          transform: 'rotate(-90deg)',
          overflow: 'visible'
        }}
      >
        {/* Background track */}
        <circle
          cx="80"
          cy="80"
          r={RADIUS}
          fill="none"
          stroke="rgba(148, 163, 184, 0.1)"
          strokeWidth={STROKE_WIDTH}
        />

        {/* Status segments */}
        {segments.map((segment, index) => (
          <circle
            key={index}
            cx="80"
            cy="80"
            r={RADIUS}
            fill="none"
            stroke={segment.color}
            strokeWidth={STROKE_WIDTH}
            strokeDasharray={`${segment.length} ${CIRCUMFERENCE}`}
            strokeDashoffset={-segment.offset}
            style={{ filter: segment.glow }}
          />
        ))}
      </svg>

      {/* Center text */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center'
        }}
      >
        <div style={{ fontSize: '32px', fontWeight: 700, color: '#dde4f0' }}>
          {stats.total}
        </div>
        <div
          style={{
            fontSize: '11px',
            color: '#7a8aaa',
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}
        >
          Total
        </div>
      </div>
    </div>
  );
}
