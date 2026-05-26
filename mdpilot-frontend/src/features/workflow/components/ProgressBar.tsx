interface Props {
  percent: number;
  stage: string;
  eta: number;
}

function formatEta(seconds: number): string {
  if (seconds < 60) {
    return `~${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  return `~${minutes}m`;
}

export function ProgressBar({ percent, stage, eta }: Props) {
  return (
    <div className="space-y-2">
      <div className="text-xs text-text-2">
        <strong>Stage:</strong> {stage}
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-bg-3">
        <div
          className="h-full rounded-full bg-gradient-to-r from-yellow-400 to-yellow-600 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      <div className="flex justify-between text-xs text-text-3">
        <span>Progress: {percent}%</span>
        <span>ETA: {formatEta(eta)}</span>
      </div>
    </div>
  );
}
