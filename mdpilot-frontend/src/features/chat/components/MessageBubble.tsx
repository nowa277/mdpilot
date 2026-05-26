import type { ChatMessage } from '@shared/types';
import { cn } from '@shared/utils';
import React from 'react';

import { useCopyToClipboard } from '../hooks/useCopyToClipboard';
import { deriveMessageStatus } from '../utils/deriveMessageStatus';
import { AgentStreamMessage } from './AgentStreamMessage';
import { MarkdownRenderer } from './MarkdownRenderer';
import { MessageAvatar } from './MessageAvatar';
import { MessageStatusBadge } from './MessageStatusBadge';
import { ThinkingBlock } from './ThinkingBlock';

interface Props {
  message: ChatMessage;
}

export const MessageBubble = React.memo(function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  const { copied, copy } = useCopyToClipboard();
  const status = deriveMessageStatus(message);

  const handleCopy = () => {
    copy(message.content || '');
  };

  // timestamp formatting
  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div
      data-role={message.role}
      className={cn('message', isUser ? 'user-message' : 'agent-message')}
    >
      {/* avatar */}
      {(message.role === 'user' || message.role === 'assistant') && (
        <MessageAvatar role={message.role} />
      )}

      {/* message content */}
      <div className="message-content">
     {/* message header */}
      <div className="message-header">
          <span className="message-author">
            {isUser ? 'USER' : 'MDPilot'}
          </span>
          <span className="message-time">
            {formatTime(message.createdAt)}
          </span>
          {status && <MessageStatusBadge status={status} />}
        </div>

        {/* message body */}
        {message.role === 'user' ? (
     <div className="message-text whitespace-pre-wrap">
            {message.content}
          </div>
     ) : message.agentBlocks ? (
          <AgentStreamMessage
            blocks={message.agentBlocks}
            {...(message.interrupted !== undefined && {
            interrupted: message.interrupted,
            })}
          />
        ) : (
          <div>
            {message.reasoning && (
              <ThinkingBlock
           reasoning={message.reasoning}
                defaultOpen={!!message.reasoning && !message.content}
              />
            )}
        {message.content && <MarkdownRenderer source={message.content} />}
          </div>
        )}
      </div>

      {/* copy button */}
      <div className="message-actions">
        <button
          type="button"
          onClick={handleCopy}
          className="action-btn"
          title="copy"
        >
          {copied ? '✓' : '📋'}
        </button>
      </div>
    </div>
  );
});
