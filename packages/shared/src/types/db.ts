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
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  company_id: string;
  full_name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
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
