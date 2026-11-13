"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { getCurrentSession, getRoleDashboardPath } from "@/lib/auth";
import { isDemoEnabled } from "@/lib/config";
import { Mail, Lock, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { DownloadAppButton } from "../components/DownloadAppButton";

export default function LoginPage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [useMagicLink, setUseMagicLink] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);

  const demoAvailable = isDemoEnabled();

  // Check if already logged in
  useEffect(() => {
    getCurrentSession().then((session) => {
      if (session) {
        router.replace(getRoleDashboardPath(session.user.role));
      }
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
            emailRedirectTo: `${window.location.origin}/auth/callback`,
          },
        });
        if (error) throw error;
        setInfoMsg(
          "Check your email for the magic login link! Click it to sign in instantly."
        );
      } else if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback`,
          },
        });
        if (error) throw error;

        if (data.session) {
          router.replace("/onboarding");
        } else {
          setInfoMsg(
            "Account created! Please check your email inbox to verify your address, or sign in below."
          );
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) {
          if (
            error.message.toLowerCase().includes("email not confirmed") ||
            error.message.toLowerCase().includes("invalid login credentials")
          ) {
            // Provide clear advice if email confirmation is pending
            throw new Error(
              error.message.toLowerCase().includes("email not confirmed")
                ? "Your email is not verified yet. Please check your inbox for the confirmation email, or choose 'Use magic link' below to sign in directly."
                : "Invalid email or password. Please verify your credentials or use magic link."
            );
          }
          throw error;
        }

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

  async function handleGoogleLogin() {
    setErrorMsg(null);
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
          queryParams: {
            access_type: "offline",
            prompt: "consent",
          },
        },
      });
      if (error) throw error;
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to initiate Google sign in.");
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 bg-slate-50 font-sans text-slate-800">
      <div className="w-full max-w-md space-y-6">
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

        {/* Credentials Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
          <h2 className="text-base font-bold text-slate-900 mb-1">
            {isSignUp ? "Create an Account" : "Sign In with Credentials"}
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            Enter your college or organization email
          </p>

          {/* Google OAuth Button */}
          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2.5 rounded-xl border border-slate-200 bg-white py-2.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 hover:border-slate-300 transition focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:opacity-50"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
            <span>Continue with Google</span>
          </button>

          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-slate-400">
                Or continue with email
              </span>
            </div>
          </div>

          <form onSubmit={handleAuth} className="space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email Address
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@college.edu or name@company.com"
                  className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition"
                />
              </div>
            </div>

            {!useMagicLink && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Password
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                    <Lock className="h-4 w-4" />
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-xs font-semibold text-white shadow-2xs hover:bg-indigo-700 transition focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Processing...</span>
                </>
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

          <div className="mt-4 flex flex-col items-center gap-1.5 text-xs">
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

          {/* Secondary "Try the demo" button - shown only when demo is enabled */}
          {demoAvailable && (
            <div className="mt-6 pt-5 border-t border-slate-100">
              <div className="text-center mb-2.5">
                <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                  Or explore instantly
                </span>
              </div>
              <Link
                href="/demo"
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-gradient-to-r from-indigo-50/70 to-blue-50/70 px-4 py-2.5 text-xs font-bold text-indigo-700 hover:bg-indigo-100/70 hover:border-indigo-300 transition shadow-2xs"
              >
                <Sparkles className="h-4 w-4 text-indigo-600" />
                <span>Try the demo</span>
              </Link>
            </div>
          )}
        </div>

        {/* Mobile App Download Card */}
        <DownloadAppButton variant="card" />
      </div>
    </div>
  );
}
