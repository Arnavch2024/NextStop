"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import { getRoleDashboardPath } from "@/lib/auth";
import { ProfileRole, completeOnboarding } from "@recruiting/shared";
import {
  GraduationCap,
  Building2,
  Briefcase,
  UserCheck,
  Loader2,
  CheckCircle2,
} from "lucide-react";

interface RoleOption {
  role: ProfileRole;
  title: string;
  badge: string;
  description: string;
  icon: typeof GraduationCap;
}

const ROLES: RoleOption[] = [
  {
    role: "student",
    title: "Student",
    badge: "Batch 2027 / 2028",
    description:
      "Mumbai college student self-reporting details and discovering campus placements.",
    icon: GraduationCap,
  },
  {
    role: "placement_officer",
    title: "Placement Officer",
    badge: "College Placement Cell",
    description:
      "Managing college profile, departments, and cohort student records effortlessly.",
    icon: Building2,
  },
  {
    role: "company",
    title: "Company",
    badge: "Hiring Organization",
    description:
      "Register company details, hiring requirements, and recruiting coordinators.",
    icon: Briefcase,
  },
  {
    role: "recruiter",
    title: "Recruiter",
    badge: "Talent Acquisition",
    description:
      "Individual recruiter connecting student talent with relevant corporate roles.",
    icon: UserCheck,
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [loadingRole, setLoadingRole] = useState<ProfileRole | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setSessionToken(session.access_token);

      // If user already has a configured role, route directly to their dashboard
      const { data: profile } = await supabase
        .from("profiles")
        .select("role")
        .eq("id", session.user.id)
        .single();
      if (profile?.role) {
        router.replace(getRoleDashboardPath(profile.role));
      }
    });
  }, [router, supabase]);

  async function selectRole(role: ProfileRole) {
    if (!sessionToken) return;
    setLoadingRole(role);
    setErrorMsg(null);
    setStatusMsg(null);

    try {
      const res = await completeOnboarding(API_BASE_URL, sessionToken, {
        role,
      });
      setStatusMsg(res.message);
      setTimeout(() => {
        router.replace(getRoleDashboardPath(res.role));
      }, 800);
    } catch (err: any) {
      // Resilient fallback: directly update Supabase profiles table
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (session?.user?.id) {
          const { error: directErr } = await supabase.from("profiles").upsert({
            id: session.user.id,
            role,
            updated_at: new Date().toISOString(),
          });

          if (!directErr) {
            setStatusMsg("Role saved successfully! Directing to dashboard...");
            setTimeout(() => {
              router.replace(getRoleDashboardPath(role));
            }, 800);
            return;
          }
        }
      } catch (fallbackErr) {
        console.warn("Direct profile update fallback failed:", fallbackErr);
      }

      setErrorMsg(
        err?.message || "Failed to set profile role. Please try again."
      );
      setLoadingRole(null);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-3xl">
        <div className="mb-8 text-center">
          <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-600">
            Step 1 of 1
          </span>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900">
            Choose Your Role
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            One tap sets your profile. Everything else is conversational through
            the AI agent.
          </p>
        </div>

        {errorMsg && (
          <div className="mb-6 rounded-xl bg-red-50 p-4 text-sm text-red-600">
            {errorMsg}
          </div>
        )}

        {statusMsg && (
          <div className="mb-6 flex items-center gap-2 rounded-xl bg-emerald-50 p-4 text-sm font-medium text-emerald-700">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span>{statusMsg}</span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {ROLES.map((item) => {
            const Icon = item.icon;
            const isLoading = loadingRole === item.role;

            return (
              <button
                key={item.role}
                type="button"
                onClick={() => selectRole(item.role)}
                disabled={loadingRole !== null}
                className="group relative flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:border-indigo-500 hover:shadow-md disabled:opacity-50"
              >
                <div>
                  <div className="mb-4 flex items-center justify-between">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 transition group-hover:bg-indigo-600 group-hover:text-white">
                      <Icon className="h-6 w-6" />
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                      {item.badge}
                    </span>
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 group-hover:text-indigo-600">
                    {item.title}
                  </h2>
                  <p className="mt-2 text-sm text-slate-500 leading-relaxed">
                    {item.description}
                  </p>
                </div>

                <div className="mt-6 flex items-center justify-end">
                  {isLoading ? (
                    <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
                  ) : (
                    <span className="text-xs font-semibold text-indigo-600 group-hover:underline">
                      Select Role &rarr;
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
