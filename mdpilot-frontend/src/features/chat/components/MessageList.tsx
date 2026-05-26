import type { ChatMessage } from '@shared/types';
import { ScrollArea } from '@shared/ui';
import { useEffect, useRef } from 'react';

import { MessageBubble } from './MessageBubble';

interface Props {
  messages: ChatMessage[];
}

export function MessageList({ messages }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const lastMsg = messages[messages.length - 1];
  const lastContent = lastMsg?.content;
  const lastReasoning = lastMsg?.reasoning;
  const lastAgentBlocks = lastMsg?.agentBlocks;
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, lastContent, lastReasoning, lastAgentBlocks]);

  return (
    <ScrollArea className="flex-1 px-6 py-4">
      <div className="mx-auto flex w-full max-w-[860px] flex-col">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={endRef} />
   </div>
    </ScrollArea>
  );
}
