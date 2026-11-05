import type { ChatRequest, ChatResponse, HealthResponse } from '../types/api';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Strips trailing slashes from base URL.
 */
function cleanBaseUrl(base: string): string {
  return base.replace(/\/+$/, '');
}

/**
 * Health check endpoint: GET /health
 */
export async function health(baseUrl: string): Promise<HealthResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/health`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(res.status, `Health check failed with status ${res.status}`, errorBody);
  }

  return (await res.json()) as HealthResponse;
}

/**
 * Conversational agent endpoint: POST /v1/chat
 */
export async function chat(baseUrl: string, message: string, token: string): Promise<ChatResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/chat`;
  const body: ChatRequest = { message };

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    const message = errorBody?.detail || `API request failed with status ${res.status}`;
    throw new ApiError(res.status, message, errorBody);
  }

  return (await res.json()) as ChatResponse;
}
