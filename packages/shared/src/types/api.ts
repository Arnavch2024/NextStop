/**
 * API Contract Types matching the FastAPI OpenAPI specification (/openapi.json)
 */

export interface HealthResponse {
  status: string;
  version: string;
  time: string;
}

export interface ChatRequest {
  message: string;
}

export type AgentStepType = 'tool_call' | 'tool_result' | 'final_reply';

export interface AgentStep {
  type: AgentStepType;
  tool?: string | null;
  input?: Record<string, any> | null;
  output?: Record<string, any> | null;
  at?: string | null;
}

export interface RecordRef {
  table: string;
  id?: string | null;
  op: 'created' | 'updated';
}

export interface ChatResponse {
  reply: string;
  steps: AgentStep[];
  records_created: RecordRef[];
}

