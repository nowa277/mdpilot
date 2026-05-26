export interface ToolExecution {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startTime: number;
  endTime?: number;
  duration?: number;
  params: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
  backend?: {
    node: string;
    resources: string;
  };
  progress?: {
    percent: number;
    stage: string;
    eta: number;
  };
  outputFiles?: string[];
}

export interface WorkflowStatistics {
  total: number;
  completed: number;
  running: number;
  failed: number;
  pending: number;
}

export interface ToolCardProps {
  tool: ToolExecution;
}
