import { getSupabaseBrowserClient, API_BASE_URL } from "./supabase";
import { demoLogin, DemoLoginResponse } from "@recruiting/shared";

export interface UserSession {
  token: string;
  user: {
    id: string;
    email?: string;
    role: string;
    displayName: string;
    collegeId?: string | null;
    companyId?: string | null;
    isDemo?: boolean;
  };
}

export async function getCurrentSession(): Promise<UserSession | null> {
  const supabase = getSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) return null;

  const { data: profile } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", session.user.id)
    .single();

  return {
    token: session.access_token,
    user: {
      id: session.user.id,
      email: session.user.email,
      role: profile?.role || "student",
      displayName:
        profile?.display_name || session.user.email?.split("@")[0] || "User",
      collegeId: profile?.college_id,
      companyId: profile?.company_id,
      isDemo: Boolean(profile?.is_demo),
    },
  };
}

export async function logout(): Promise<void> {
  const supabase = getSupabaseBrowserClient();
  await supabase.auth.signOut();
}

export async function loginWithDemoRole(role: string): Promise<UserSession> {
  const data: DemoLoginResponse = await demoLogin(API_BASE_URL, role);
  const supabase = getSupabaseBrowserClient();

  if (data.access_token && data.refresh_token) {
    await supabase.auth.setSession({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    });
  }

  return {
    token: data.access_token,
    user: {
      id: data.user.id,
      email: data.user.email,
      role: data.user.role,
      displayName: data.user.display_name,
      collegeId: data.user.college_id,
      companyId: data.user.company_id,
      isDemo: true,
    },
  };
}

export function getRoleDashboardPath(role?: string | null): string {
  switch (role) {
    case "placement_officer":
      return "/officer/home";
    case "company":
      return "/company/home";
    case "recruiter":
      return "/chat";
    case "student":
      return "/home";
    default:
      return "/onboarding";
  }
}
