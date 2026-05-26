// Placeholder types — will be regenerated from backend openapi.json in Phase 1C.
// These cover only what Phase 1A/1B mocks need.

export type ChatId = string;
export type TaskId = string;
export type MessageId = string;

export type TaskStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type TaskKind = 'alphafold2' | 'amber_md' | 'mmpbsa' | 'bioreason' | 'report';

// Agent block types for streaming agent messages
export type AgentBlock =
  | { type: 'thinking'; content: string }
  | {
      type: 'tool_call';
      tool_call_id?: string;
      name: string;
      input?: unknown;
    status: 'pending' | 'running' | 'completed' | 'failed';
      result?: string;
      error?: string;
      backend?: {
        node: 'lab02' | 'lab03' | 'lab06';
      gpuInfo?: string;
      };
    }
  | { type: 'tool_result'; name: string; result: string }
  | { type: 'progress'; message: string; percent?: number }
  | { type: 'error'; message: string }
  | { type: 'response'; content: string }
  | { type: 'streaming'; content: string };

export interface ToolQueueItem {
  id: string;
  tool: string;
  order: number;
  label: string;
  constraints?: Record<string, unknown>;
  name?: string;
  input?: unknown;
  status?: 'pending' | 'running' | 'completed' | 'failed';
  result?: string;
  error?: string;
}

export interface ToolModuleConfig {
  id: string;
  tool: string;
  label: string;
  description: string;
  route: string;
  tags: string[];
  defaults?: Record<string, unknown>;
  enabled: boolean;
  name?: string;
  config?: Record<string, unknown>;
}

export interface Chat {
  id: ChatId;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessage {
  id: MessageId;
  chatId: ChatId;
  role: 'user' | 'assistant' | 'system';
  content: string;
  reasoning?: string;  // GLM-5 thinking/reasoning content
  agentBlocks?: AgentBlock[];  // Agent workspace blocks
  interrupted?: boolean;  // Agent message was interrupted
  createdAt: string;
}

export interface Task {
  id: TaskId;
  chatId: ChatId;
  kind: TaskKind;
  status: TaskStatus;
  progress: number;
  startedAt?: string;
  finishedAt?: string;
  error?: string;
}

export interface Artifact {
  chatId: ChatId;
  kind: 'pdb' | 'dcd' | 'csv' | 'png' | 'log' | 'report';
  filename: string;
  sizeBytes: number;
  producedAt: string;
}

export interface GPUInfo {
  id: string;
  model: string;
  usedMB: number;
  totalMB: number;
  tempC?: number;
  utilization?: number;
  powerDraw?: number;
  powerLimit?: number;
}

export interface NodeStatus {
  id: 'lab02' | 'lab06' | 'lab03';
  online: boolean;
  gpu?: GPUInfo;
  gpus?: GPUInfo[];
  queueDepth: number;
  lastSeen: string;
}

export interface SkillInfo {
  name: string;
  title: string;
  description: string;
  tags: string[];
  source: string;
}

export interface Settings {
  llm: {
    endpoint: string;
    apiToken?: string;
    model: string;
    temperature: number;
    maxTokens: number;
  };
}
