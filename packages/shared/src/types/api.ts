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

export type AgentStepType =
  "tool_call" | "tool_result" | "final_reply" | "search_summary";

export interface AgentStep {
  type: AgentStepType | string;
  tool?: string | null;
  input?: Record<string, any> | null;
  output?: Record<string, any> | null;
  summary?: string | null;
  at?: string | null;
}

export interface RecordRef {
  table: string;
  id?: string | null;
  op: "created" | "updated" | "merged";
}

export interface ChatResponse {
  reply: string;
  steps: AgentStep[];
  records_created: RecordRef[];
  contacts?: ContactCard[];
}

export interface TranscribeResponse {
  text: string;
}

export interface BreakdownItem {
  reason: string;
  points: number;
  source: "resume" | "user_said" | "system";
}

export interface ScoreResponse {
  score: number;
  breakdown: BreakdownItem[];
  next_best_actions: string[];
}

export interface ResumeResponse {
  document_id: string;
  signed_url: string;
  records_created: RecordRef[];
  missing_fields: string[];
  score: ScoreResponse;
}

export interface StudentRecord {
  id: string;
  profile_id: string;
  college_id?: string | null;
  full_name: string;
  batch_year: number;
  degree?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface EducationRecord {
  id: string;
  student_id: string;
  profile_id: string;
  level: "tenth" | "twelfth" | "bachelors" | "masters" | "other";
  institution?: string | null;
  degree?: string | null;
  branch?: string | null;
  board_or_university?: string | null;
  score_value?: number | null;
  score_scale?: "percentage" | "gpa10" | "cgpa10" | "cgpa4" | null;
  start_year?: number | null;
  end_year?: number | null;
  source: string;
  confidence: number;
}

export interface InternshipRecord {
  id: string;
  student_id: string;
  profile_id: string;
  company?: string | null;
  company_id?: string | null;
  role?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration_months?: number | null;
  source: string;
  confidence: number;
}

export interface JobRecord {
  id: string;
  student_id: string;
  profile_id: string;
  company?: string | null;
  company_id?: string | null;
  role?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration_months?: number | null;
  source: string;
  confidence: number;
}

export interface SkillRecord {
  id: string;
  student_id: string;
  profile_id: string;
  name: string;
  proficiency?: string | null;
  source: string;
  confidence: number;
}

export interface DocumentRecord {
  id: string;
  student_id: string;
  profile_id: string;
  kind: "resume" | "id_proof" | "certificate" | "other";
  storage_path: string;
  file_name?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  verification_status: "pending" | "pre_verified" | "rejected";
  uploaded_at: string;
}

export interface StudentProfile {
  student: StudentRecord | null;
  education: EducationRecord[];
  internships: InternshipRecord[];
  jobs: JobRecord[];
  skills: SkillRecord[];
  documents: DocumentRecord[];
}

export interface ContactSourceModel {
  source: string;
  source_url?: string | null;
  domain?: string | null;
  fetched_at?: string | null;
  confidence: number;
}

export interface ContactCard {
  id: string;
  name: string;
  title?: string | null;
  company_id?: string | null;
  company_name?: string | null;
  college_id?: string | null;
  college_name?: string | null;
  role_type: string;
  email?: string | null;
  linkedin_url?: string | null;
  location?: string | null;
  source?: string | null;
  source_url?: string | null;
  source_published_date?: string | null;
  stale?: boolean | null;
  confidence?: number | null;
  unverified?: boolean;
  saved: boolean;
  is_sample: boolean;
  sources: ContactSourceModel[];
  first_seen_at?: string | null;
  last_verified_at?: string | null;
}

export interface ContactListResponse {
  items: ContactCard[];
  page: number;
  page_size: number;
  total: number;
}

export interface SaveResponse {
  contact_id: string;
  saved: boolean;
}

export interface SaveContactRequest {
  phone?: string | null;
}

export interface OutreachDraftRequest {
  contact_id: string;
  channel: "email" | "linkedin";
  sender_context?: string | null;
}

export interface OutreachDraftResponse {
  draft_id: string;
  subject?: string | null;
  body: string;
  channel: string;
}

export interface AgentRunResponse {
  id: string;
  status: string;
  steps: Record<string, any>[];
  summary?: string | null;
  created_at?: string | null;
}

// --- Day 4 Models ---

export interface CampusScoreResponse {
  campus_score: number;
  campus_internship_score: number;
  breakdown: BreakdownItem[];
  flagged: string[];
  next_best_actions: string[];
}

export interface CompanyScoreResponse {
  score: number;
  breakdown: BreakdownItem[];
  next_best_actions: string[];
}

export interface ImportReport {
  imported: number;
  skipped: number;
  reasons: string[];
}

export interface StudentCard {
  id: string;
  full_name: string;
  branch?: string | null;
  degree?: string | null;
  score_value?: number | null;
  score_scale?: string | null;
  batch_year: number;
  college_name?: string | null;
  college_id?: string | null;
  current_status: string;
  student_score?: number | null;
  unverified: boolean;
}

export interface StudentListResponse {
  items: any[];
  total: number;
  page: number;
  page_size: number;
  status_counts?: Record<string, number> | null;
}

export interface CampusHiringRecord {
  id: string;
  company_id?: string | null;
  college_id: string;
  college_name?: string | null;
  cycle_year: number;
  type: string;
  students_interviewed: number;
  offers_made: number;
  created_at?: string | null;
}

export interface DemoAccount {
  role: string;
  display_name: string;
  email: string;
  description: string;
  college_id?: string | null;
  company_id?: string | null;
}

export interface DemoLoginResponse {
  access_token: string;
  refresh_token?: string | null;
  expires_at?: number | null;
  token_type: string;
  user: {
    id: string;
    email: string;
    role: string;
    display_name: string;
    college_id?: string | null;
    company_id?: string | null;
    is_demo: boolean;
  };
}

export interface LetterDraftRequest {
  kind: "invitation" | "interview" | "offer";
  contact_id: string;
  channel?: "email" | "linkedin";
  sender_context?: string | null;
}

export interface LetterDraftResponse {
  draft_id: string;
  subject?: string | null;
  body: string;
  channel: string;
  kind: string;
}

export interface BatchShareResponse {
  college_id: string;
  batch_year: number;
  shared_with_recruiters: boolean;
}
