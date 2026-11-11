"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import {
  getStudentScore,
  getStudentProfile,
  getTimeline,
  ScoreResponse,
  StudentProfile,
  TimelineStation,
} from "@recruiting/shared";
import {
  Award,
  Calendar,
  CheckCircle2,
  ChevronRight,
  Loader2,
  MessageSquare,
  Sparkles,
  TrendingUp,
  Smartphone,
  X,
  ShieldCheck,
  Building2,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";
import { RailwayTimeline } from "@/app/components/RailwayTimeline";
import { PreVerifySheet } from "@/app/components/PreVerifySheet";
import { ReferenceAuthSheet } from "@/app/components/ReferenceAuthSheet";

export default function StudentHomePage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [scoreData, setScoreData] = useState<ScoreResponse | null>(null);
  const [profileData, setProfileData] = useState<StudentProfile | null>(null);
  const [timelineStations, setTimelineStations] = useState<TimelineStation[]>(
    []
  );
  const [syncToast, setSyncToast] = useState<string | null>(null);

  // Modals state
  const [isPreVerifyOpen, setIsPreVerifyOpen] = useState(false);
  const [isRefAuthOpen, setIsRefAuthOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;
    let toastTimeout: NodeJS.Timeout | null = null;

    async function loadData(token: string) {
      try {
        const [scoreRes, profileRes, timelineRes] = await Promise.all([
          getStudentScore(API_BASE_URL, token),
          getStudentProfile(API_BASE_URL, token),
          getTimeline(API_BASE_URL, token).catch(() => ({ stations: [] })),
        ]);

        if (isMounted) {
          setScoreData(scoreRes);
          setProfileData(profileRes);
          setTimelineStations(timelineRes.stations || []);
          setLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Failed to load profile and score.");
          setLoading(false);
        }
      }
    }

    const activeChannels: any[] = [];

    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!isMounted) return;
      if (!session) {
        router.replace("/login");
        return;
      }

      const { data: profile } = await supabase
        .from("profiles")
        .select("role")
        .eq("id", session.user.id)
        .single();

      if (!profile?.role) {
        router.replace("/onboarding");
        return;
      }
      if (profile.role !== "student") {
        router.replace(
          profile.role === "placement_officer"
            ? "/officer/home"
            : profile.role === "company"
              ? "/company/home"
              : "/chat"
        );
        return;
      }

      const token = session.access_token;
      const userId = session.user.id;
      setSessionToken(token);
      loadData(token);

      const triggerToastAndReload = (msg = "Updated from your phone") => {
        if (!isMounted) return;
        setSyncToast(msg);
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
          if (isMounted) setSyncToast(null);
        }, 4000);
        loadData(token);
      };

      const chanId = Math.random().toString(36).slice(2, 7);

      const scoreChan = supabase
        .channel(`home_score_${userId}_${chanId}`)
        .on(
          "postgres_changes",
          {
            event: "INSERT",
            schema: "public",
            table: "score_events",
            filter: `profile_id=eq.${userId}`,
          },
          (payload) => {
            const sc = (payload.new as any)?.score;
            triggerToastAndReload(
              sc !== undefined
                ? `Score updated to ${sc} from your phone`
                : "Updated from your phone"
            );
          }
        )
        .subscribe();

      const profileChan = supabase
        .channel(`home_profile_${userId}_${chanId}`)
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "education",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Profile updated from your phone")
        )
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "internships",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Profile updated from your phone")
        )
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "skills",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Profile updated from your phone")
        )
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "reference_authorizations",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Reference check authorization updated")
        )
        .subscribe();

      if (!isMounted) {
        supabase.removeChannel(scoreChan);
        supabase.removeChannel(profileChan);
      } else {
        activeChannels.push(scoreChan, profileChan);
      }
    });

    return () => {
      isMounted = false;
      if (toastTimeout) clearTimeout(toastTimeout);
      activeChannels.forEach((c) => supabase.removeChannel(c));
    };
  }, [router, supabase]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          <p className="text-sm text-slate-500 font-medium">
            Loading your profile...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-xl shadow p-6 text-center">
          <p className="text-red-600 font-medium mb-4">{error}</p>
          <Link
            href="/chat"
            className="inline-flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            Go to Chat
          </Link>
        </div>
      </div>
    );
  }

  const score = scoreData?.score ?? 20;
  const breakdown = scoreData?.breakdown ?? [];
  const nextActions = scoreData?.next_best_actions ?? [];

  const student = profileData?.student;
  const internships = profileData?.internships ?? [];
  const documents = profileData?.documents ?? [];

  // Day 5 status flags
  const verifiedDoc = documents.find((d) => d.verified_flag);
  const isPreVerified =
    !!verifiedDoc ||
    breakdown.some(
      (b) =>
        b.reason.toLowerCase().includes("pre-verified") ||
        b.reason.toLowerCase().includes("identity document")
    );
  const hasUploadedDocs = documents.length > 0;
  const maskedTail = verifiedDoc?.masked_id_tail;

  const isRefAuthorized = breakdown.some(
    (b) =>
      b.reason.toLowerCase().includes("reference check") ||
      b.reason.toLowerCase().includes("reference-check")
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16 relative">
      {/* Realtime Sync Toast */}
      {syncToast && (
        <div className="fixed top-20 right-6 z-50 flex items-center gap-2.5 rounded-xl border border-blue-200 bg-white px-4 py-3 text-xs font-medium text-slate-800 shadow-xl animate-in fade-in slide-in-from-top-4">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-blue-600">
            <Smartphone className="h-3.5 w-3.5" />
          </div>
          <div>
            <p className="font-semibold text-slate-900">{syncToast}</p>
            <p className="text-[10px] text-slate-400">Synced live</p>
          </div>
          <button
            onClick={() => setSyncToast(null)}
            className="ml-2 text-slate-400 hover:text-slate-600"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-slate-900">
              Student Dashboard
            </h1>
            <p className="text-xs text-slate-500">
              {student?.full_name
                ? `${student.full_name} • Batch ${student.batch_year}`
                : "Campus Recruiting"}
            </p>
          </div>
          <Link
            href="/chat"
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition"
          >
            <MessageSquare className="w-4 h-4" />
            <span>Chat Assistant</span>
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 pt-6 space-y-6">
        {/* Score & Next Action Card */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-1 bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Readiness Score
                </span>
                <Award className="w-5 h-5 text-amber-500" />
              </div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-5xl font-extrabold text-blue-600">
                  {score}
                </span>
                <span className="text-sm font-semibold text-slate-400">
                  / 100
                </span>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-100">
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                />
              </div>
            </div>
          </div>

          <div className="md:col-span-2 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 p-6 rounded-2xl shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 text-blue-800 text-xs font-semibold uppercase tracking-wider">
                <Sparkles className="w-4 h-4" />
                <span>Next Best Action</span>
              </div>
              <p className="mt-2 text-base font-medium text-slate-800">
                {nextActions[0] ||
                  "Your profile is looking great! Chat with the assistant to keep it updated."}
              </p>
            </div>
            <div className="mt-4">
              <Link
                href="/chat"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 hover:text-blue-900"
              >
                <span>Complete now in chat</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>

        {/* Day 5 Cards: Pre-Verification & Reference Check */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Pre-Verify Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Document Pre-Verification
                    </h3>
                    <p className="text-xs text-slate-500">
                      Demo verification (mocked)
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {isPreVerified ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Verified (mocked)</span>
                    </span>
                  ) : hasUploadedDocs ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                      <span>Uploaded</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
                      <span>Not verified</span>
                    </span>
                  )}
                </div>
              </div>

              {maskedTail && (
                <div className="mt-3 bg-slate-50 border border-slate-200/80 rounded-xl p-2.5 text-xs text-slate-700 flex items-center justify-between">
                  <span className="text-slate-500">Masked ID Identifier:</span>
                  <span className="font-mono font-semibold text-slate-900">
                    {maskedTail}
                  </span>
                </div>
              )}

              <p className="mt-2 text-xs text-slate-500 leading-relaxed">
                Pre-verify your sample credentials to claim +2 readiness points.
                The application never reads file contents or authentic ID
                numbers.
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs font-semibold text-indigo-600">
                {isPreVerified ? "+2 points awarded" : "+2 points available"}
              </span>
              <button
                type="button"
                onClick={() => setIsPreVerifyOpen(true)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 transition"
              >
                {isPreVerified ? "Manage Documents" : "Pre-Verify Document"}
              </button>
            </div>
          </div>

          {/* Reference Check Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                    <Award className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Reference Check
                    </h3>
                    <p className="text-xs text-slate-500">
                      Internship employer outreach
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {isRefAuthorized ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Authorized</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
                      <span>Not authorized</span>
                    </span>
                  )}
                </div>
              </div>

              <p className="mt-3 text-xs text-slate-600 leading-relaxed">
                Authorizing lets verified recruiters and placement officers
                contact your internship company to confirm your experience.
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs font-semibold text-amber-700">
                {isRefAuthorized ? "+2 points awarded" : "+2 points available"}
              </span>
              <button
                type="button"
                onClick={() => setIsRefAuthOpen(true)}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 text-white hover:bg-amber-700 transition"
              >
                {isRefAuthorized
                  ? "Manage Authorization"
                  : "Authorize Outreach"}
              </button>
            </div>
          </div>
        </div>

        {/* Why is my score N? (Breakdown) */}
        <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-slate-900">
              Why is my score {score}?
            </h2>
          </div>

          <div className="divide-y divide-slate-100">
            {breakdown.map((item, idx) => {
              const isPreVerifyItem =
                item.reason.toLowerCase().includes("pre-verified") ||
                item.reason.toLowerCase().includes("identity document");

              return (
                <div
                  key={idx}
                  className="py-3 flex items-center justify-between text-sm"
                >
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                    <div>
                      <span className="font-medium text-slate-800">
                        {item.reason}
                      </span>
                      {isPreVerifyItem && (
                        <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                          Demo verification (mocked)
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-mono">
                      {item.source}
                    </span>
                  </div>
                  <span className="font-bold text-emerald-600">
                    +{item.points}
                  </span>
                </div>
              );
            })}
          </div>

          {nextActions.length > 1 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Additional Ways to Improve
              </h3>
              <ul className="space-y-1.5 text-xs text-slate-600 list-disc list-inside">
                {nextActions.slice(1).map((act, i) => (
                  <li key={i}>{act}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {/* Railway Timeline from GET /v1/students/me/timeline */}
        <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5 text-indigo-600" />
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Railway Career Journey
                </h2>
                <p className="text-xs text-slate-500">
                  Stations chronologically ordered along your professional route
                </p>
              </div>
            </div>
          </div>

          <RailwayTimeline stations={timelineStations} isLoading={loading} />
        </section>
      </main>

      {/* Day 5 Pre-Verify Sheet */}
      <PreVerifySheet
        isOpen={isPreVerifyOpen}
        onClose={() => setIsPreVerifyOpen(false)}
        token={sessionToken || ""}
        baseUrl={API_BASE_URL}
        documents={documents}
        onSuccess={(sc) => {
          if (sc) setScoreData(sc);
          if (sessionToken) {
            getStudentProfile(API_BASE_URL, sessionToken)
              .then(setProfileData)
              .catch(() => {});
            getTimeline(API_BASE_URL, sessionToken)
              .then((t) => setTimelineStations(t.stations || []))
              .catch(() => {});
          }
        }}
      />

      {/* Day 5 Reference Check Authorization Sheet */}
      <ReferenceAuthSheet
        isOpen={isRefAuthOpen}
        onClose={() => setIsRefAuthOpen(false)}
        token={sessionToken || ""}
        baseUrl={API_BASE_URL}
        internships={internships}
        isAuthorized={isRefAuthorized}
        onSuccess={(sc) => {
          if (sc) setScoreData(sc);
          if (sessionToken) {
            getTimeline(API_BASE_URL, sessionToken)
              .then((t) => setTimelineStations(t.stations || []))
              .catch(() => {});
          }
        }}
      />
    </div>
  );
}
