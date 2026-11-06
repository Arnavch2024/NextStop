import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  ResumeResponse,
  ScoreResponse,
  StudentProfile,
  TranscribeResponse,
} from '../types/api';

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

/**
 * Student score endpoint: GET /v1/students/me/score
 */
export async function getStudentScore(baseUrl: string, token: string): Promise<ScoreResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/students/me/score`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(res.status, errorBody?.detail || 'Failed to fetch student score', errorBody);
  }

  return (await res.json()) as ScoreResponse;
}

/**
 * Student profile endpoint: GET /v1/students/me/profile
 */
export async function getStudentProfile(baseUrl: string, token: string): Promise<StudentProfile> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/students/me/profile`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(res.status, errorBody?.detail || 'Failed to fetch student profile', errorBody);
  }

  return (await res.json()) as StudentProfile;
}

/**
 * Voice transcribe endpoint: POST /v1/voice/transcribe
 */
export async function transcribeAudio(
  baseUrl: string,
  audioBlob: any,
  filename: string,
  token: string
): Promise<TranscribeResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/voice/transcribe`;
  const formData = new FormData();
  formData.append('audio', audioBlob, filename);

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(res.status, errorBody?.detail || 'Transcription failed', errorBody);
  }

  return (await res.json()) as TranscribeResponse;
}
