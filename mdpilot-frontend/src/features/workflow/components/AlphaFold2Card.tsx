import { useEffect, useState } from 'react';

import type { ToolCardProps } from '../types';
import { ProgressBar } from './ProgressBar';
import { StatusBadge } from './StatusBadge';

function formatDuration(ms: number): string {
  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function truncateSequence(sequence: string, maxLength: number = 50): string {
  if (sequence.length <= maxLength) {
    return sequence;
  }
  return sequence.slice(0, maxLength) + '...';
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

function getPlddtColor(score: number): string {
  if (score >= 90) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-500';
  return 'bg-red-500';
}

interface PlddtScoresProps {
  scores: number[];
}

function PlddtScores({ scores }: PlddtScoresProps) {
  const bestModelIndex = scores.indexOf(Math.max(...scores));

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-text-2">pLDDT Scores</div>
   <div className="space-y-1.5">
        {scores.map((score, index) => (
          <div key={index} className="flex items-center gap-2">
            <span className="w-16 text-xs text-text-2">
              Model {index + 1}
              {index === bestModelIndex && ' ⭐'}
         </span>
         <div className="flex-1 h-4 overflow-hidden rounded-full bg-bg-3">
            <div
         className={`h-full ${getPlddtColor(score)} transition-all duration-300`}
                style={{ width: `${score}%` }}
           />
            </div>
         <span className="w-10 text-xs text-text-2 text-right">{score}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
export function AlphaFold2Card({ tool }: ToolCardProps) {
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

  const sequence = tool.params.sequence as string | undefined;
  const plddtScores = tool.result?.plddt_scores as number[] | undefined;

  return (
    <div
      className="rounded-lg p-4 bg-bg-2/40 backdrop-blur-sm"
      style={STATUS_STYLES[tool.status]}
    >
      <div className="space-y-3">
        {/* Header: Tool name with DNA icon and status */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text-1">
            🧬 {tool.name}
          </h3>
          <StatusBadge status={tool.status} />
        </div>

        {/* Backend info */}
        {tool.backend && (
          <div className="text-xs text-text-2">
            <strong>Backend:</strong> {tool.backend.node} ({tool.backend.resources})
          </div>
        )}

        {/* Progress bar (only when running) */}
        {tool.status === 'running' && tool.progress && (
        <ProgressBar
            percent={tool.progress.percent}
            stage={tool.progress.stage}
            eta={tool.progress.eta}
          />
        )}

        {/* Input sequence */}
        {sequence && (
          <div className="space-y-1">
        <div className="text-xs font-semibold text-text-2">Input Sequence</div>
            <div className="overflow-x-auto rounded bg-bg-3 p-2 font-mono text-xs text-text-2">
              {truncateSequence(sequence)}
            </div>
       </div>
        )}

        {/* pLDDT scores visualization */}
        {tool.status === 'completed' && plddtScores && plddtScores.length === 5 && (
        <PlddtScores scores={plddtScores} />
        )}

        {/* Error (only when failed) */}
        {tool.status === 'failed' && tool.error && (
          <div className="space-y-1">
       <div className="text-xs font-semibold text-red-600">Error</div>
       <div className="rounded bg-red-50 p-2 text-xs text-red-700 dark:bg-red-900/20 dark:text-red-400">
          {tool.error}
            </div>
          </div>
        )}

        {/* Duration and output files */}
        <div className="flex items-center justify-between text-xs text-text-3">
          <div>
                {tool.duration !== undefined ? (
        <span>Duration: {formatDuration(tool.duration)}</span>
       ) : tool.status === 'running' ? (
              <span>⏱ {formatDuration(elapsed)} elapsed</span>
       ) : null}
          </div>
          {tool.outputFiles && tool.outputFiles.length > 0 && (
            <div>
           <strong>Output Files:</strong> {tool.outputFiles.length} files
        </div>
      )}
        </div>
      </div>
    </div>
  );
}
