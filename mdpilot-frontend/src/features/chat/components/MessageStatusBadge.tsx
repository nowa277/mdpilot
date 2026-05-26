import { cn } from '@shared/utils';

import type { MessageStatus } from '../utils/deriveMessageStatus';

interface Props {
  status: Exclude<MessageStatus, null>;
}

const statusConfig = {
  completed: {
    label: 'completed',
    className: 'status-success',
  },
  running: {
    label: 'running',
    className: 'status-running',
  },
  error: {
    label: 'error',
    className: 'status-error',
  },
} as const;

export function MessageStatusBadge({ status }: Props) {
  const config = statusConfig[status];

  return (
    <span className={cn('message-status', config.className)}>
      <span className="status-dot" />
      {config.label}
    </span>
  );
}
