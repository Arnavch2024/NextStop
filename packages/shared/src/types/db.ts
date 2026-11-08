/**
 * Supabase Database Schemas matching the design spec & 001_init.sql
 */

export type ProfileRole =
  "student" | "placement_officer" | "company" | "recruiter";

export type AgentRunStatus = "running" | "completed" | "failed";

export interface Profile {
  id: string;
  role: ProfileRole | null;
  display_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface College {
  id: string;
  name: string;
  city: string;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: string;
  name: string;
  industry: string | null;
  category?: string | null;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

export type ContactRoleType =
  "campus_recruiter" | "placement_officer" | "hr" | "other";

export interface Contact {
  id: string;
  company_id: string | null;
  college_id: string | null;
  name: string;
  title: string | null;
  role_type: ContactRoleType;
  email: string | null;
  linkedin_url: string | null;
  source: string;
  source_url: string | null;
  confidence: number;
  phone?: string | null;
  owner_id?: string | null;
  created_by_profile_id: string | null;
  first_seen_at: string;
  last_verified_at: string | null;
  suppressed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContactSource {
  id: string;
  contact_id: string;
  source: "seed" | "resume" | "user_said" | "web";
  source_url: string | null;
  fetched_at: string | null;
  confidence: number;
  unverified: boolean;
  note: string | null;
  created_at: string;
}

export interface SearchCache {
  id: string;
  query_hash: string;
  query: string;
  provider: string;
  purpose: string | null;
  result: any;
  expires_at: string;
  created_at: string;
}

export interface UserSavedContact {
  id: string;
  profile_id: string;
  contact_id: string;
  saved_at: string;
  note: string | null;
  phone: string | null;
  user_overrides: Record<string, any> | null;
  unverified: boolean;
  created_at: string;
}

export interface OutreachDraft {
  id: string;
  profile_id: string;
  contact_id: string | null;
  channel: "email" | "linkedin";
  subject: string | null;
  body: string;
  created_at: string;
}

export interface Student {
  id: string;
  profile_id: string;
  college_id: string | null;
  full_name: string;
  batch_year: 2027 | 2028;
  degree: string | null;
  created_at: string;
  updated_at: string;
}

export type RawEventSource =
  "user_message" | "agent_message" | "tool_call" | "tool_result";

export interface RawEvent {
  id: string;
  payload: Record<string, any>;
  source: RawEventSource;
  source_url: string | null;
  actor_id: string | null;
  created_at: string;
}

export interface AgentRun {
  id: string;
  profile_id: string;
  status: AgentRunStatus;
  steps: Record<string, any>[];
  created_at: string;
  updated_at: string;
}
