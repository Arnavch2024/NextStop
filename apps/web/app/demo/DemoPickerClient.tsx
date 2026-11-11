"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { loginWithDemoRole, getRoleDashboardPath } from "@/lib/auth";
import {
  GraduationCap,
  Building2,
  Briefcase,
  UserCheck,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Sparkles,
  ShieldAlert,
  AlertTriangle,
} from "lucide-react";

interface DemoRoleConfig {
  role: string;
  badge: string;
  displayName: string;
  description: string;
  whatToTry: string;
  icon: typeof GraduationCap;
  accentBg: string;
  accentText: string;
  badgeBg: string;
}

const DEMO_ROLES: DemoRoleConfig[] = [
  {
    role: "student",
    badge: "Student",
    displayName: "Aarav Sharma",
    description:
      "Final Year B.Tech Computer Engineering student (Batch 2027) at SPIT Mumbai.",
    whatToTry:
      "View your Readiness Score, explore the Mumbai railway milestone timeline, and mock pre-verify your student identity.",
    icon: GraduationCap,
    accentBg: "bg-blue-600",
    accentText: "text-blue-600",
    badgeBg: "bg-blue-50 text-blue-700 border-blue-200",
  },
  {
    role: "placement_officer",
    badge: "Placement Officer",
    displayName: "Prof. Sunita Patil",
    description:
      "Training & Placement Officer managing campus batches and students at VJTI Mumbai.",
    whatToTry:
      "Toggle batch sharing permissions, review student readiness breakdowns, and track campus recruitment stats.",
    icon: Building2,
    accentBg: "bg-indigo-600",
    accentText: "text-indigo-600",
    badgeBg: "bg-indigo-50 text-indigo-700 border-indigo-200",
  },
  {
    role: "company",
    badge: "Company Partner",
    displayName: "Pooja Sharma",
    description:
      "University Relations Lead evaluating college talent and campus cycles across Mumbai.",
    whatToTry:
      "Upload hiring history CSVs, calculate company hiring score, and search opted-in campus students.",
    icon: Briefcase,
    accentBg: "bg-cyan-600",
    accentText: "text-cyan-600",
    badgeBg: "bg-cyan-50 text-cyan-700 border-cyan-200",
  },
  {
    role: "recruiter",
    badge: "Talent Recruiter",
    displayName: "Karan Mehta",
    description:
      "Early careers talent specialist sourcing top university graduates.",
    whatToTry:
      "Use conversational AI assistant to search student profiles, filter by score, and bookmark candidates to My List.",
    icon: UserCheck,
    accentBg: "bg-emerald-600",
    accentText: "text-emerald-600",
    badgeBg: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
];

export default function DemoPickerClient() {
  const router = useRouter();
  const [loadingRole, setLoadingRole] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function handleSelectRole(role: string) {
    setLoadingRole(role);
    setErrorMsg(null);
    try {
      const session = await loginWithDemoRole(role);
      router.replace(getRoleDashboardPath(session.user.role));
    } catch (err: any) {
      setErrorMsg(
        err?.message ||
          "Demo login failed. Make sure DEMO_LOGIN_ENABLED is enabled."
      );
      setLoadingRole(null);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-800">
      {/* Required Demo Banner */}
      <aside
        aria-label="Demo notice"
        className="bg-amber-50 border-b border-amber-200 px-4 py-2.5 text-center text-xs font-medium text-amber-900 flex items-center justify-center gap-2"
      >
        <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
        <span>
          Demo accounts use sample data. Verification is mocked. Nothing is ever
          sent.
        </span>
      </aside>

      {/* Top Header / Back Link */}
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-2xs">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <span className="text-sm font-bold text-slate-900 tracking-tight">
                Campus Recruiting
              </span>
              <span className="ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-700 uppercase tracking-wider">
                Demo
              </span>
            </div>
          </div>

          <Link
            href="/login"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-indigo-600 transition shadow-2xs"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to normal login</span>
          </Link>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8 sm:py-12">
        <div className="text-center max-w-xl mx-auto mb-8 sm:mb-10">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Choose a Demo Persona
          </h1>
          <p className="mt-2 text-sm text-slate-600 leading-relaxed">
            Experience the platform from four distinct campus recruiting roles.
            Each role provides access to pre-seeded demo records in an isolated
            sandbox.
          </p>
        </div>

        {errorMsg && (
          <div className="max-w-xl mx-auto mb-6 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs text-red-800">
            <ShieldAlert className="h-4 w-4 shrink-0 text-red-600 mt-0.5" />
            <div>
              <p className="font-semibold">Unable to start demo session</p>
              <p className="mt-0.5">{errorMsg}</p>
            </div>
          </div>
        )}

        {/* 4 Role Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 max-w-4xl mx-auto">
          {DEMO_ROLES.map((item) => {
            const Icon = item.icon;
            const isLoggingIn = loadingRole === item.role;
            const isDisabled = loadingRole !== null;

            return (
              <div
                key={item.role}
                className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-sm hover:border-indigo-300 hover:shadow-md transition-all duration-200"
              >
                <div>
                  {/* Card Header: Icon + Badge */}
                  <div className="flex items-center justify-between mb-4">
                    <div
                      className={`flex h-11 w-11 items-center justify-center rounded-xl ${item.accentBg} text-white shadow-2xs`}
                    >
                      <Icon className="h-6 w-6" />
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${item.badgeBg}`}
                    >
                      {item.badge}
                    </span>
                  </div>

                  {/* Display Name & One-line description */}
                  <h2 className="text-base font-bold text-slate-900">
                    {item.displayName}
                  </h2>
                  <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                    {item.description}
                  </p>

                  {/* "What to try" line */}
                  <div className="mt-4 rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                    <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                      What to try
                    </p>
                    <p className="text-xs text-slate-700 leading-normal">
                      {item.whatToTry}
                    </p>
                  </div>
                </div>

                {/* Login Action Button */}
                <div className="mt-6 pt-4 border-t border-slate-100">
                  <button
                    type="button"
                    disabled={isDisabled}
                    onClick={() => handleSelectRole(item.role)}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-indigo-700 transition shadow-2xs disabled:opacity-50"
                  >
                    {isLoggingIn ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Opening demo session...</span>
                      </>
                    ) : (
                      <>
                        <span>Continue as {item.badge}</span>
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Security / Isolation Disclaimer Footer */}
        <div className="mt-10 text-center">
          <p className="text-[11px] text-slate-400">
            Demo sessions operate strictly in an isolated sandbox. Live web
            search and external communications are disabled.
          </p>
        </div>
      </main>
    </div>
  );
}
