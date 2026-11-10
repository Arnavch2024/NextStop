"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import { getRoleDashboardPath } from "@/lib/auth";
import { completeOnboarding } from "@recruiting/shared";
import { Loader2 } from "lucide-react";

export default function AuthCallbackPage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    async function processCallback() {
      try {
        // Exchange code if PKCE query parameter 'code' is present
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get("code");

        if (code) {
          const { error: exchangeError } =
            await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) throw exchangeError;
        }

        const {
          data: { session },
          error: sessionError,
        } = await supabase.auth.getSession();

        if (sessionError) throw sessionError;
        if (!session) {
          router.replace("/login");
          return;
        }

        // Query user profile from public.profiles
        const { data: profile, error: profileError } = await supabase
          .from("profiles")
          .select("role")
          .eq("id", session.user.id)
          .single();

        if (profileError && profileError.code !== "PGRST116") {
          console.warn("Could not load user profile:", profileError);
        }

        // Direct to onboarding if no role is chosen yet, else sync and route to role dashboard
        if (!profile?.role) {
          router.replace("/onboarding");
        } else {
          try {
            const res = await completeOnboarding(
              API_BASE_URL,
              session.access_token,
              { role: profile.role as any }
            );
            router.replace(getRoleDashboardPath(res.role));
          } catch {
            router.replace(getRoleDashboardPath(profile.role));
          }
        }
      } catch (err: any) {
        setErrorMsg(
          err?.message || "Authentication failed. Redirecting to login..."
        );
        setTimeout(() => {
          router.replace("/login");
        }, 2500);
      }
    }

    processCallback();
  }, [router, supabase]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 bg-slate-50">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-sm text-center">
        {errorMsg ? (
          <div className="text-xs text-red-600 bg-red-50 p-3 rounded-xl border border-red-200">
            {errorMsg}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
            <p className="text-xs font-semibold text-slate-700">
              Verifying Google sign in...
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
