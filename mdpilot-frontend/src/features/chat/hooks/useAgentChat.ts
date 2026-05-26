/**
 * useAgentChat — fetch-streaming to Agent SSE endpoint.
 */
import { readEnv } from '@shared/config';
import type { AgentBlock } from '@shared/types';
import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

import { parseAgentSseFrames } from '../api/agent-sse-parse';
import { notifyAgentComplete } from '../notifications';
import { useChatUiStore } from '../store/chat-ui.store';
import type { ChatId } from '../types';
import {
  appendAgentMessageStart,
  appendAssistantError,
  markAgentMessageInterrupted,
  replaceStreamingBlocks,
  upsertAgentBlock,
} from './messages-cache';

export interface AgentChatHandle {
  send: (prompt: string) => void;
  stop: () => void;
  state: 'closed' | 'open';
}

export function useAgentChat(chatId: ChatId | null): AgentChatHandle {
  const qc = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);
  const msgIdRef = useRef<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  // Abort any in-flight stream when chatId changes or component unmounts
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, [chatId]);

  const stop = useCallback(() => {
    if (abortRef.current && msgIdRef.current && chatId) {
      abortRef.current.abort();
      markAgentMessageInterrupted(qc, chatId, msgIdRef.current);
      msgIdRef.current = null;
      setIsStreaming(false);
    }
  }, [chatId, qc]);

  const send = useCallback(
    (prompt: string) => {
      if (!chatId || !prompt) return;

      const env = readEnv();
      if (env.mode === 'mock') {
        appendAssistantError(qc, chatId, '⚠️ Agent 调用失败: mock mode not supported');
        return;
      }

      // Get tool queue and enabled tools from Zustand store
      const { toolQueue, toolModules } = useChatUiStore.getState();

      const manualQueue = toolQueue.map((item) => ({
        tool: item.tool,
        order: item.order,
        enabled: true,
        constraints: item.constraints ?? {},
      }));

    const enabledTools = toolModules
        .filter((m) => m.enabled)
        .map((m) => m.tool);

      const payload = {
        session_id: chatId,
        prompt,
      mode: 'agent',
        manual_queue: manualQueue,
        enabled_tools: enabledTools,
      };

      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (env.apiToken) headers['Authorization'] = `Bearer ${env.apiToken}`;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const msgId = `agent-${crypto.randomUUID()}`;
      msgIdRef.current = msgId;
      let started = false;
      setIsStreaming(true);

      void (async () => {
        let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
        try {
          const url = `${env.apiBase}/api/v1/agent/stream`;
          const resp = await fetch(url, {
            method: 'POST',
            headers,
       body: JSON.stringify(payload),
            signal: controller.signal,
          });

          if (!resp.ok) {
          const text = await resp.text();
            throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
          }

          reader = resp.body?.getReader();
          if (!reader) throw new Error('No response body');

          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
         if (done) break;
          buffer += decoder.decode(value, { stream: true });

            const { events, buffer: newBuffer } = parseAgentSseFrames(buffer, '');
            buffer = newBuffer;

            for (const frame of events) {
              // Handle message_split: create new message bubble
              if (frame.event === 'message_split') {
                const newMsgId = `agent-${crypto.randomUUID()}`;
                appendAgentMessageStart(qc, chatId, newMsgId);
                msgIdRef.current = newMsgId;
                continue;
              }

              // First frame: create initial message
              if (!started) {
                appendAgentMessageStart(qc, chatId, msgId);
                started = true;
              }

              const blockWithId = convertFrameToBlock(frame);
              if (blockWithId) {
                upsertAgentBlock(qc, chatId, msgIdRef.current!, blockWithId);
              }
              // Replace streaming blocks with classified thinking/response blocks
              if (frame.event === 'thinking_block' || frame.event === 'response_block') {
                const blockType = frame.event === 'thinking_block' ? 'thinking' : 'response';
                const content = String((frame.data as Record<string, unknown>).content ?? '');
                replaceStreamingBlocks(qc, chatId, msgIdRef.current!, { type: blockType, content } as any);
              }
              if (frame.event === 'complete') {
                notifyAgentComplete(String(frame.data.result ?? 'Agent task completed'));
              }
            }
          }

          // Flush remaining buffer
          if (buffer.trim()) {
            const { events } = parseAgentSseFrames(buffer, '');
            for (const frame of events) {
              // Handle message_split: create new message bubble
              if (frame.event === 'message_split') {
                const newMsgId = `agent-${crypto.randomUUID()}`;
                appendAgentMessageStart(qc, chatId, newMsgId);
                msgIdRef.current = newMsgId;
                continue;
              }

              if (!started) {
                appendAgentMessageStart(qc, chatId, msgId);
                started = true;
              }
              const blockWithId = convertFrameToBlock(frame);
              if (blockWithId) {
                upsertAgentBlock(qc, chatId, msgIdRef.current!, blockWithId);
              }
              // Replace streaming blocks with classified thinking/response blocks
              if (frame.event === 'thinking_block' || frame.event === 'response_block') {
                const blockType = frame.event === 'thinking_block' ? 'thinking' : 'response';
                const content = String((frame.data as Record<string, unknown>).content ?? '');
                replaceStreamingBlocks(qc, chatId, msgIdRef.current!, { type: blockType, content } as any);
              }
              if (frame.event === 'complete') {
                notifyAgentComplete(String(frame.data.result ?? 'Agent task completed'));
              }
            }
          }
        } catch (err) {
       if (err instanceof Error && err.name === 'AbortError') {
        // Release the stream lock so the underlying connection can be cleaned up
            try {
        await reader?.cancel();
            } catch {
              /* ignore */
          }
            return;
          }
          const message = err instanceof Error ? err.message : String(err);
          appendAssistantError(qc, chatId, `⚠️ Agent 调用失败: ${message}`);
        } finally {
          msgIdRef.current = null;
          setIsStreaming(false);
      }
      })();
    },
    [chatId, qc],
  );

  return { send, stop, state: isStreaming ? 'open' : 'closed' };
}

function convertFrameToBlock(frame: {
  event: string;
  data: Record<string, unknown>;
}): { block: AgentBlock; toolCallId?: string } | null {
  switch (frame.event) {
    case 'thinking':
   return {
        block: {
          type: 'thinking',
          content: String(frame.data.content ?? ''),
        },
      };
    case 'llm_response': {
      const content = String(frame.data?.content ?? '');
      if (!content) return null;
      return { block: { type: 'streaming', content } };
    }
    // Remove 'tool_call' case - it's a low-level event without tool_call_id
    // We only handle 'tool_started' which has tool_call_id
    case 'tool_started': {
      const block: Extract<AgentBlock, { type: 'tool_call' }> = {
        type: 'tool_call',
        name: String(frame.data.tool ?? ''),
        status: 'running',
        input: frame.data.input as Record<string, unknown> | undefined,
      };
      if ((frame.data.backend as Record<string, unknown>)?.node)
        block.backend = frame.data.backend as { node: 'lab02' | 'lab03' | 'lab06'; gpuInfo?: string };
      const toolCallId = frame.data.tool_call_id ? String(frame.data.tool_call_id) : undefined;
      return toolCallId ? { block, toolCallId } : { block };
    }
    case 'tool_completed': {
      const block: Extract<AgentBlock, { type: 'tool_call' }> = {
        type: 'tool_call',
        name: String(frame.data.tool ?? ''),
        status: 'completed',
        result: String(frame.data.output ?? ''),
      };
      if ((frame.data.backend as Record<string, unknown>)?.node)
        block.backend = frame.data.backend as { node: 'lab02' | 'lab03' | 'lab06'; gpuInfo?: string };
      const toolCallId = frame.data.tool_call_id ? String(frame.data.tool_call_id) : undefined;
      return toolCallId ? { block, toolCallId } : { block };
    }
    case 'tool_failed': {
      const block: Extract<AgentBlock, { type: 'tool_call' }> = {
        type: 'tool_call',
        name: String(frame.data.tool ?? ''),
        status: 'failed',
        error: String(frame.data.error ?? ''),
      };
      if ((frame.data.backend as Record<string, unknown>)?.node)
        block.backend = frame.data.backend as { node: 'lab02' | 'lab03' | 'lab06'; gpuInfo?: string };
      const toolCallId = frame.data.tool_call_id ? String(frame.data.tool_call_id) : undefined;
      return toolCallId ? { block, toolCallId } : { block };
    }
    case 'tool_retrying': {
      const block: Extract<AgentBlock, { type: 'tool_call' }> = {
        type: 'tool_call',
        name: String(frame.data.tool ?? ''),
        status: 'running',
      };
      if ((frame.data.backend as Record<string, unknown>)?.node)
        block.backend = frame.data.backend as { node: 'lab02' | 'lab03' | 'lab06'; gpuInfo?: string };
      const toolCallId = frame.data.tool_call_id ? String(frame.data.tool_call_id) : undefined;
      return toolCallId ? { block, toolCallId } : { block };
    }
    case 'error':
      return {
        block: {
          type: 'error',
          message: String(frame.data.error ?? ''),
        },
      };
    case 'complete':
      // The complete event's result duplicates llm_response content.
      // Skip creating a response block here; the notification is handled separately.
      return null;
    case 'iteration_start':
    case 'loop_end':
    case 'message_split':
    case 'thinking_block':
    case 'response_block':
      return null;
    default:
   return null;
  }
}
