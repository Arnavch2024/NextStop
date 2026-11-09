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

const DEMO_SESSION_KEY = "demo_session";

export function getDemoSession(): UserSession | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(DEMO_SESSION_KEY);
  if (!raw) return null;
  try {
    const data: DemoLoginResponse = JSON.parse(raw);
    return {
      token: data.access_token,
      user: {
        id: data.user.id,
        email: data.user.email,
        role: data.user.role,
        displayName: data.user.display_name,
        collegeId: data.user.college_id,
        companyId: data.user.company_id,
        isDemo: data.user.is_demo,
      },
    };
  } catch {
    return null;
  }
}

export async function getCurrentSession(): Promise<UserSession | null> {
  const demoSession = getDemoSession();
  if (demoSession) return demoSession;

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
      isDemo: false,
    },
  };
}

export async function logout(): Promise<void> {
  if (typeof window !== "undefined") {
    localStorage.removeItem(DEMO_SESSION_KEY);
  }
  const supabase = getSupabaseBrowserClient();
  await supabase.auth.signOut();
}

export async function loginWithDemoRole(role: string): Promise<UserSession> {
  const data: DemoLoginResponse = await demoLogin(API_BASE_URL, role);
  if (typeof window !== "undefined") {
    localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify(data));
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
