"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import { getRoleDashboardPath } from "@/lib/auth";
import { completeOnboarding } from "@recruiting/shared";

export default function HomePage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function handleLanding() {
      try {
        // 1. Check if Supabase redirected here with hash fragments (#access_token=...&refresh_token=...)
        if (typeof window !== "undefined" && window.location.hash) {
          const hashClean = window.location.hash.replace(/^#/, "");
          const hashParams = new URLSearchParams(hashClean);
          const accessToken = hashParams.get("access_token");
          const refreshToken = hashParams.get("refresh_token");

          if (accessToken && refreshToken) {
            const { error: sessionError } = await supabase.auth.setSession({
              access_token: accessToken,
              refresh_token: refreshToken,
            });
            if (sessionError) {
              console.error("Failed to set session from hash:", sessionError);
            }
          }
        }

        // 2. Check if Supabase redirected here with PKCE code (?code=...)
        if (typeof window !== "undefined" && window.location.search) {
          const urlParams = new URLSearchParams(window.location.search);
          const code = urlParams.get("code");
          if (code) {
            const { error: exchangeError } =
              await supabase.auth.exchangeCodeForSession(code);
            if (exchangeError) {
              console.error(
                "Failed to exchange code for session:",
                exchangeError
              );
            }
          }
        }

        // 3. Inspect active session
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session) {
          if (mounted) router.replace("/login");
          return;
        }

        // 4. Query user profile
        const { data: profile, error: profileError } = await supabase
          .from("profiles")
          .select("role")
          .eq("id", session.user.id)
          .single();

        let userRole = profile?.role;

        // Auto-provision profile if missing
        if (!profile && profileError && profileError.code === "PGRST116") {
          const fallbackName =
            session.user.user_metadata?.full_name ||
            session.user.user_metadata?.name ||
            session.user.email?.split("@")[0] ||
            "User";

          const { data: newProfile } = await supabase
            .from("profiles")
            .upsert({
              id: session.user.id,
              display_name: fallbackName,
              updated_at: new Date().toISOString(),
            })
            .select("role")
            .single();

          userRole = newProfile?.role;
        }

        if (!userRole) {
          if (mounted) router.replace("/onboarding");
          return;
        }

        // Sync onboarding state with backend if needed
        try {
          await completeOnboarding(API_BASE_URL, session.access_token, {
            role: userRole as any,
          });
        } catch {
          // Backend sync non-blocking
        }

        if (mounted) {
          router.replace(getRoleDashboardPath(userRole));
        }
      } catch (err) {
        console.error("Error during home session resolution:", err);
        if (mounted) router.replace("/login");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    handleLanding();

    return () => {
      mounted = false;
    };
  }, [router, supabase]);

  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent" />
        <p className="text-sm font-medium text-slate-500">
          Loading your dashboard...
        </p>
      </div>
    </div>
  );
}
