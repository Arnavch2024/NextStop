import type {
  AgentRunResponse,
  ChatRequest,
  ChatResponse,
  ContactListResponse,
  HealthResponse,
  OutreachDraftRequest,
  OutreachDraftResponse,
  ResumeResponse,
  SaveContactRequest,
  SaveResponse,
  ScoreResponse,
  StudentProfile,
  TranscribeResponse,
} from "../types/api";

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Strips trailing slashes from base URL.
 */
function cleanBaseUrl(base: string): string {
  return base.replace(/\/+$/, "");
}

/**
 * Health check endpoint: GET /health
 */
export async function health(baseUrl: string): Promise<HealthResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/health`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      `Health check failed with status ${res.status}`,
      errorBody
    );
  }

  return (await res.json()) as HealthResponse;
}

/**
 * Conversational agent endpoint: POST /v1/chat
 */
export async function chat(
  baseUrl: string,
  message: string,
  token: string
): Promise<ChatResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/chat`;
  const body: ChatRequest = { message };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    const message =
      errorBody?.detail || `API request failed with status ${res.status}`;
    throw new ApiError(res.status, message, errorBody);
  }

  return (await res.json()) as ChatResponse;
}

/**
 * Student score endpoint: GET /v1/students/me/score
 */
export async function getStudentScore(
  baseUrl: string,
  token: string
): Promise<ScoreResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/students/me/score`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Failed to fetch student score",
      errorBody
    );
  }

  return (await res.json()) as ScoreResponse;
}

/**
 * Student profile endpoint: GET /v1/students/me/profile
 */
export async function getStudentProfile(
  baseUrl: string,
  token: string
): Promise<StudentProfile> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/students/me/profile`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Failed to fetch student profile",
      errorBody
    );
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
  if (audioBlob && typeof audioBlob === "object" && audioBlob.uri) {
    formData.append("audio", audioBlob as any);
  } else {
    formData.append("audio", audioBlob, filename);
  }

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Transcription failed",
      errorBody
    );
  }

  return (await res.json()) as TranscribeResponse;
}

/**
 * Upload resume endpoint: POST /v1/students/me/resume
 */
export async function uploadResume(
  baseUrl: string,
  file: any,
  filename: string,
  token: string
): Promise<ResumeResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/students/me/resume`;
  const formData = new FormData();
  if (file && typeof file === "object" && file.uri) {
    // React Native FormData asset
    formData.append("file", file as any);
  } else {
    // Browser File/Blob
    formData.append("file", file, filename);
  }

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Resume upload failed",
      errorBody
    );
  }

  return (await res.json()) as ResumeResponse;
}

/**
 * Save contact endpoint: POST /v1/contacts/{id}/save
 */
export async function saveContact(
  baseUrl: string,
  contactId: string,
  token: string,
  body?: SaveContactRequest
): Promise<SaveResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/contacts/${contactId}/save`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body || {}),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Failed to save contact",
      errorBody
    );
  }

  return (await res.json()) as SaveResponse;
}

/**
 * Remove saved contact endpoint: DELETE /v1/contacts/{id}/save
 */
export async function removeSavedContact(
  baseUrl: string,
  contactId: string,
  token: string
): Promise<SaveResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/contacts/${contactId}/save`;
  const res = await fetch(url, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Failed to remove saved contact",
      errorBody
    );
  }

  return (await res.json()) as SaveResponse;
}

export interface ListContactsParams {
  q?: string;
  company_id?: string;
  college_id?: string;
  role_type?: string;
  saved_only?: boolean;
  include_sample?: boolean;
  page?: number;
  page_size?: number;
}

/**
 * List contacts endpoint: GET /v1/contacts
 */
export async function listContacts(
  baseUrl: string,
  token: string,
  params?: ListContactsParams
): Promise<ContactListResponse> {
  const cleanBase = cleanBaseUrl(baseUrl);
  const searchParams = new URLSearchParams();

  if (params) {
    if (params.q !== undefined && params.q !== null && params.q !== "") {
      searchParams.append("q", params.q);
    }
    if (params.company_id) {
      searchParams.append("company_id", params.company_id);
    }
    if (params.college_id) {
      searchParams.append("college_id", params.college_id);
    }
    if (params.role_type) {
      searchParams.append("role_type", params.role_type);
    }
    if (params.saved_only !== undefined && params.saved_only !== null) {
      searchParams.append("saved_only", String(params.saved_only));
    }
    if (params.include_sample !== undefined && params.include_sample !== null) {
      searchParams.append("include_sample", String(params.include_sample));
    }
    if (params.page !== undefined && params.page !== null) {
      searchParams.append("page", String(params.page));
    }
    if (params.page_size !== undefined && params.page_size !== null) {
      searchParams.append("page_size", String(params.page_size));
    }
  }

  const queryStr = searchParams.toString();
  const url = queryStr
    ? `${cleanBase}/v1/contacts?${queryStr}`
    : `${cleanBase}/v1/contacts`;

  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Failed to fetch contacts",
      errorBody
    );
  }

  return (await res.json()) as ContactListResponse;
}

/**
 * Outreach draft endpoint: POST /v1/outreach/draft
 */
export async function draftOutreach(
  baseUrl: string,
  token: string,
  body: OutreachDraftRequest
): Promise<OutreachDraftResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/outreach/draft`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Failed to draft outreach message",
      errorBody
    );
  }

  return (await res.json()) as OutreachDraftResponse;
}

/**
 * Agent run detail endpoint: GET /v1/agent-runs/{id}
 */
export async function getAgentRun(
  baseUrl: string,
  runId: string,
  token: string
): Promise<AgentRunResponse> {
  const url = `${cleanBaseUrl(baseUrl)}/v1/agent-runs/${runId}`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      errorBody?.detail || "Failed to fetch agent run",
      errorBody
    );
  }

  return (await res.json()) as AgentRunResponse;
}
