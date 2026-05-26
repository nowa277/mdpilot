import { useWorkflowStore } from '@features/workflow/store/workflow.store';
import { useEffect } from 'react';

import type { ChatId } from '../types';

/**
 * Syncs active chat ID to workflow store when chat changes.
 */
export function useActiveChatSync(chatId: ChatId | null) {
  const setActiveChat = useWorkflowStore((s) => s.setActiveChat);

  useEffect(() => {
    setActiveChat(chatId);
  }, [chatId, setActiveChat]);
}
