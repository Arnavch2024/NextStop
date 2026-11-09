import type {
  ChatRequest,
  ChatResponse,
  ContactListResponse,
  HealthResponse,
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
 * List contacts endpoint: GET /v1/contacts
 */
export async function listContacts(
  baseUrl: string,
  params: {
    q?: string;
    company_id?: string;
    college_id?: string;
    role_type?: string;
    saved_only?: boolean;
    page?: number;
    page_size?: number;
  },
  token: string
): Promise<ContactListResponse> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.company_id) query.set("company_id", params.company_id);
  if (params.college_id) query.set("college_id", params.college_id);
  if (params.role_type) query.set("role_type", params.role_type);
  if (params.saved_only) query.set("saved_only", "true");
  if (params.page) query.set("page", params.page.toString());
  if (params.page_size) query.set("page_size", params.page_size.toString());

  const url = `${cleanBaseUrl(baseUrl)}/v1/contacts?${query.toString()}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiError(res.status, "Failed to load contacts");
  return (await res.json()) as ContactListResponse;
}

/**
 * Demo accounts: GET /v1/auth/demo-accounts
 */
export async function getDemoAccounts(baseUrl: string) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/auth/demo-accounts`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new ApiError(res.status, "Failed to load demo accounts");
  return await res.json();
}

/**
 * Demo login: POST /v1/auth/demo-login
 */
export async function demoLogin(baseUrl: string, role: string) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/auth/demo-login`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err.detail || "Demo login failed", err);
  }
  return await res.json();
}

/**
 * College score: GET /v1/colleges/{id}/score
 */
export async function getCollegeScore(
  baseUrl: string,
  collegeId: string,
  token: string
) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/colleges/${collegeId}/score`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiError(res.status, "Failed to load college score");
  return await res.json();
}

/**
 * Company score: GET /v1/companies/{id}/score
 */
export async function getCompanyScore(
  baseUrl: string,
  companyId: string,
  token: string
) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/companies/${companyId}/score`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiError(res.status, "Failed to load company score");
  return await res.json();
}

/**
 * Import student records: POST /v1/student-records
 */
export async function importStudentRecords(
  baseUrl: string,
  file: File | Blob,
  token: string
) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/student-records`;
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      err.detail || "Failed to import student records",
      err
    );
  }
  return await res.json();
}

/**
 * List student records: GET /v1/student-records
 */
export async function listStudentRecords(
  baseUrl: string,
  params: {
    q?: string;
    batch_year?: number;
    status?: string;
    branch?: string;
    degree?: string;
    college_id?: string;
    min_score?: number;
    page?: number;
    page_size?: number;
  },
  token: string
) {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.batch_year) query.set("batch_year", params.batch_year.toString());
  if (params.status) query.set("status", params.status);
  if (params.branch) query.set("branch", params.branch);
  if (params.degree) query.set("degree", params.degree);
  if (params.college_id) query.set("college_id", params.college_id);
  if (params.min_score !== undefined)
    query.set("min_score", params.min_score.toString());
  if (params.page) query.set("page", params.page.toString());
  if (params.page_size) query.set("page_size", params.page_size.toString());

  const url = `${cleanBaseUrl(baseUrl)}/v1/student-records?${query.toString()}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new ApiError(res.status, "Failed to load student records");
  return await res.json();
}

/**
 * Toggle batch sharing: POST /v1/colleges/me/batches/{year}/share
 */
export async function toggleBatchShare(
  baseUrl: string,
  year: number,
  shared: boolean,
  token: string
) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/colleges/me/batches/${year}/share`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ shared }),
  });
  if (!res.ok) throw new ApiError(res.status, "Failed to toggle batch sharing");
  return await res.json();
}

/**
 * Get batch sharing status: GET /v1/colleges/me/batches/shares
 */
export async function getBatchShares(baseUrl: string, token: string) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/colleges/me/batches/shares`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!res.ok)
    throw new ApiError(res.status, "Failed to load batch sharing status");
  return await res.json();
}

/**
 * Import campus hiring: POST /v1/campus-hiring
 */
export async function importCampusHiring(
  baseUrl: string,
  file: File | Blob,
  token: string
) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/campus-hiring`;
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      err.detail || "Failed to import campus hiring data",
      err
    );
  }
  return await res.json();
}

/**
 * List campus hiring: GET /v1/campus-hiring
 */
export async function listCampusHiring(
  baseUrl: string,
  params: { cycle_year?: number; type?: string },
  token: string
) {
  const query = new URLSearchParams();
  if (params.cycle_year) query.set("cycle_year", params.cycle_year.toString());
  if (params.type) query.set("type", params.type);

  const url = `${cleanBaseUrl(baseUrl)}/v1/campus-hiring?${query.toString()}`;
  const res = await fetch(url, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!res.ok)
    throw new ApiError(res.status, "Failed to load campus hiring records");
  return await res.json();
}

/**
 * Draft letter: POST /v1/outreach/letter
 */
export async function draftLetter(
  baseUrl: string,
  body: {
    kind: "invitation" | "interview" | "offer";
    contact_id: string;
    channel?: string;
    sender_context?: string;
  },
  token: string
) {
  const url = `${cleanBaseUrl(baseUrl)}/v1/outreach/letter`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, "Failed to draft letter");
  return await res.json();
}
