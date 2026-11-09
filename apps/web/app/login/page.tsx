"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import {
  getCurrentSession,
  loginWithDemoRole,
  getRoleDashboardPath,
} from "@/lib/auth";
import { getDemoAccounts, DemoAccount } from "@recruiting/shared";
import {
  Mail,
  Lock,
  ArrowRight,
  Loader2,
  Sparkles,
  Building2,
  GraduationCap,
  Briefcase,
  UserCheck,
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [useMagicLink, setUseMagicLink] = useState(false);
  const [loading, setLoading] = useState(false);
  const [demoLoadingRole, setDemoLoadingRole] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [demoAccounts, setDemoAccounts] = useState<DemoAccount[]>([]);

  // Check if already logged in or load demo accounts
  useEffect(() => {
    getCurrentSession().then((session) => {
      if (session) {
        router.replace(getRoleDashboardPath(session.user.role));
      }
    });

    getDemoAccounts(API_BASE_URL)
      .then((accounts) => {
        if (Array.isArray(accounts)) {
          setDemoAccounts(accounts);
        }
      })
      .catch(() => {
        // Demo login disabled or unavailable
        setDemoAccounts([]);
      });
  }, [router]);

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;

    setLoading(true);
    setErrorMsg(null);
    setInfoMsg(null);

    try {
      if (useMagicLink) {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: {
            emailRedirectTo: `${window.location.origin}/`,
          },
        });
        if (error) throw error;
        setInfoMsg("Check your email for the magic login link!");
      } else if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;

        if (data.session) {
          router.replace("/onboarding");
        } else {
          setInfoMsg(
            "Account created! Please check your email to verify your address or log in."
          );
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;

        const { data: profile } = await supabase
          .from("profiles")
          .select("role")
          .eq("id", data.user.id)
          .single();

        router.replace(getRoleDashboardPath(profile?.role));
      }
    } catch (err: any) {
      setErrorMsg(
        err?.message || "Authentication failed. Please check your credentials."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleDemoLogin(role: string) {
    setDemoLoadingRole(role);
    setErrorMsg(null);
    try {
      const session = await loginWithDemoRole(role);
      router.replace(getRoleDashboardPath(session.user.role));
    } catch (err: any) {
      setErrorMsg(
        err?.message ||
          "Demo login failed. Make sure DEMO_LOGIN_ENABLED is true."
      );
    } finally {
      setDemoLoadingRole(null);
    }
  }

  const getRoleIcon = (role: string) => {
    switch (role) {
      case "placement_officer":
        return <GraduationCap className="h-5 w-5 text-indigo-600" />;
      case "company":
        return <Building2 className="h-5 w-5 text-blue-600" />;
      case "recruiter":
        return <Briefcase className="h-5 w-5 text-emerald-600" />;
      default:
        return <UserCheck className="h-5 w-5 text-amber-600" />;
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 bg-slate-50">
      <div className="w-full max-w-4xl space-y-6">
        {/* Brand Header */}
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-md">
            <Sparkles className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Campus Recruiting Platform
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Mumbai College Batches 2027 & 2028
          </p>
        </div>

        {errorMsg && (
          <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700 border border-red-200">
            {errorMsg}
          </div>
        )}

        {infoMsg && (
          <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700 border border-emerald-200">
            {infoMsg}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Standard Credentials Card */}
          <div className="lg:col-span-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-bold text-slate-900 mb-1">
              {isSignUp ? "Create an Account" : "Sign In with Credentials"}
            </h2>
            <p className="text-xs text-slate-500 mb-5">
              Enter your college or organization email
            </p>

            <form onSubmit={handleAuth} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-600">
                  Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@college.edu or company.com"
                    className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
                  />
                </div>
              </div>

              {!useMagicLink && (
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
                    />
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-xs font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50 shadow-sm"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <span>
                      {useMagicLink
                        ? "Send Magic Link"
                        : isSignUp
                          ? "Create Account"
                          : "Sign In"}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-5 flex flex-col items-center gap-1.5 text-xs text-slate-500 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => setUseMagicLink(!useMagicLink)}
                className="font-medium text-indigo-600 hover:underline"
              >
                {useMagicLink
                  ? "Sign in with Password instead"
                  : "Sign in with Magic Link"}
              </button>

              {!useMagicLink && (
                <button
                  type="button"
                  onClick={() => setIsSignUp(!isSignUp)}
                  className="text-slate-600 hover:underline"
                >
                  {isSignUp
                    ? "Already have an account? Sign In"
                    : "Don't have an account? Sign Up"}
                </button>
              )}
            </div>
          </div>

          {/* Demo Account Picker */}
          <div className="lg:col-span-7 rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50/50 to-white p-6 shadow-sm">
            <div className="mb-4">
              <div className="inline-flex items-center gap-1.5 rounded-full bg-indigo-100 px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-indigo-800">
                <Sparkles className="h-3 w-3" />
                <span>Instant Demo Access</span>
              </div>
              <h2 className="text-base font-bold text-slate-900 mt-2">
                Explore as a Role (No Registration Required)
              </h2>
              <p className="text-xs text-slate-600 mt-0.5">
                Switch instantly between Day 4 persona dashboards with
                pre-seeded demo records:
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(demoAccounts.length > 0
                ? demoAccounts
                : [
                    {
                      role: "placement_officer",
                      display_name: "Dr. Rao",
                      email: "placement@vjti.ac.in",
                      description:
                        "Placement Officer at VJTI Mumbai (Batches 2027 & 2028)",
                    },
                    {
                      role: "company",
                      display_name: "TechCorp HR",
                      email: "talent@techcorp.com",
                      description:
                        "Campus Hiring Partner & Recruiter in Mumbai",
                    },
                    {
                      role: "recruiter",
                      display_name: "Acme Recruiter",
                      email: "recruiter@acmestaffing.com",
                      description:
                        "External Talent Recruiter sourcing Mumbai graduates",
                    },
                    {
                      role: "student",
                      display_name: "Aarav Sharma",
                      email: "aarav.sharma@spit.ac.in",
                      description:
                        "B.Tech Computer Engineering student (Batch 2027)",
                    },
                  ]
              ).map((acc) => {
                const isLoggingIn = demoLoadingRole === acc.role;
                return (
                  <div
                    key={acc.role}
                    className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs hover:border-indigo-300 hover:shadow-xs transition"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-700 capitalize">
                          {acc.role.replace("_", " ")}
                        </span>
                        {getRoleIcon(acc.role)}
                      </div>
                      <div className="mt-2 font-bold text-slate-900 text-xs">
                        {acc.display_name}
                      </div>
                      <p className="mt-1 text-[11px] text-slate-500 leading-normal line-clamp-2">
                        {acc.description}
                      </p>
                    </div>

                    <div className="mt-3 pt-2.5 border-t border-slate-100">
                      <button
                        type="button"
                        disabled={demoLoadingRole !== null}
                        onClick={() => handleDemoLogin(acc.role)}
                        className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 transition disabled:opacity-50"
                      >
                        {isLoggingIn ? (
                          <>
                            <Loader2 className="h-3 w-3 animate-spin" />
                            <span>Opening...</span>
                          </>
                        ) : (
                          <>
                            <span>Open {acc.role.split("_")[0]}</span>
                            <ArrowRight className="h-3 w-3" />
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="mt-4 text-[11px] text-slate-400 text-center">
              Demo sessions operate in an isolated sandbox with demo-flagged
              records only.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
