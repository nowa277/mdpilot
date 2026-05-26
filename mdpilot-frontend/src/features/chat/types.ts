import type {
  AgentBlock,
  Chat,
  ChatId,
  ChatMessage,
  MessageId,
  ToolModuleConfig,
  ToolQueueItem,
} from '@shared/types';

export type {
  AgentBlock,
  Chat,
  ChatId,
  ChatMessage,
  MessageId,
  ToolModuleConfig,
  ToolQueueItem,
};

export interface SendMessageInput {
  chatId: ChatId;
  content: string;
}

export interface ChatStreamingMessage {
  id: MessageId;
  chatId: ChatId;
  role: 'assistant';
  content: string;
  isStreaming: boolean;
}
