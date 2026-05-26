import { cn } from '@shared/utils';

interface OnlineBadgeProps {
  online: boolean;
}

export function OnlineBadge({ online }: OnlineBadgeProps) {
  return (
    <span
      className={cn(
        'inline-block rounded-chip px-2 py-0.5 text-xs font-medium',
      online ? 'bg-success/20 text-success' : 'bg-bg-2 text-text-3',
      )}
    >
      {online ? 'online' : 'offline'}
    </span>
  );
}
