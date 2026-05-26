import { cn } from '@shared/utils';

interface Props {
  role: 'user' | 'assistant';
}

export function MessageAvatar({ role }: Props) {
  const isUser = role === 'user';
  return (
    <div
      className={cn(
        'message-avatar',
        isUser ? 'user' : 'agent',
      )}
    >
      {isUser ? 'U' : 'A'}
    </div>
  );
}
