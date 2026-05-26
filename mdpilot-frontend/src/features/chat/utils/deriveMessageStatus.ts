import type { ChatMessage } from '@shared/types';

export type MessageStatus = 'completed' | 'running' | 'error' | null;

/**
 * 从消息的 agentBlocks 推导消息状态
 * @param message 聊天消息对象
 * @returns 消息状态: completed | running | error | null
 */
export function deriveMessageStatus(message: ChatMessage): MessageStatus {
  // 用户消息或无 agent 块
  if (!message.agentBlocks || message.agentBlocks.length === 0) {
    return null;
  }

  const toolCalls = message.agentBlocks.filter((b) => b.type === 'tool_call');

  // 检查是否有错误
  const hasError = message.agentBlocks.some((b) => b.type === 'error');
  const hasFailedTool = toolCalls.some((t) => t.status === 'failed');
  if (hasError || hasFailedTool) {
    return 'error';
  }

  // 检查是否有运行中的工具
  const hasRunningTool = toolCalls.some(
    (t) => t.status === 'pending' || t.status === 'running',
  );
  if (hasRunningTool) {
    return 'running';
  }

  // 所有工具都完成
  const allCompleted = toolCalls.every((t) => t.status === 'completed');
  if (allCompleted && toolCalls.length > 0) {
    return 'completed';
  }

  return null;
}
