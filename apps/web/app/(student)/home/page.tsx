'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { getSupabaseBrowserClient, API_BASE_URL } from '@/lib/supabase';
import {
  getStudentScore,
  getStudentProfile,
  ScoreResponse,
  StudentProfile,
} from '@recruiting/shared';
import {
  Award,
  BookOpen,
  Briefcase,
  Calendar,
  CheckCircle2,
  ChevronRight,
  GraduationCap,
  Loader2,
  MessageSquare,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

export default function StudentHomePage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scoreData, setScoreData] = useState<ScoreResponse | null>(null);
  const [profileData, setProfileData] = useState<StudentProfile | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session) {
          router.replace('/login');
          return;
        }

        const token = session.access_token;
        const [scoreRes, profileRes] = await Promise.all([
          getStudentScore(API_BASE_URL, token),
          getStudentProfile(API_BASE_URL, token),
        ]);

        if (isMounted) {
          setScoreData(scoreRes);
          setProfileData(profileRes);
          setLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Failed to load profile and score.');
          setLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isMounted = false;
    };
  }, [router, supabase]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          <p className="text-sm text-slate-500 font-medium">Loading your profile...</p>
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
  const education = profileData?.education ?? [];
  const internships = profileData?.internships ?? [];
  const jobs = profileData?.jobs ?? [];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-slate-900">Student Dashboard</h1>
            <p className="text-xs text-slate-500">
              {student?.full_name ? `${student.full_name} • Batch ${student.batch_year}` : 'Campus Recruiting'}
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
                <span className="text-5xl font-extrabold text-blue-600">{score}</span>
                <span className="text-sm font-semibold text-slate-400">/ 100</span>
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
                {nextActions[0] || 'Your profile is looking great! Chat with the assistant to keep it updated.'}
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

        {/* Why is my score N? (Breakdown) */}
        <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-blue-600" />
            <h2 className="text-base font-bold text-slate-900">Why is my score {score}?</h2>
          </div>

          <div className="divide-y divide-slate-100">
            {breakdown.map((item, idx) => (
              <div key={idx} className="py-3 flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                  <span className="font-medium text-slate-800">{item.reason}</span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-mono">
                    {item.source}
                  </span>
                </div>
                <span className="font-bold text-emerald-600">+{item.points}</span>
              </div>
            ))}
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

        {/* Vertical Timeline: Education -> Internships -> Jobs */}
        <section className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-6">
            <Calendar className="w-5 h-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">Profile Timeline</h2>
          </div>

          <div className="relative pl-6 border-l-2 border-indigo-200 space-y-6">
            {/* Education items */}
            {education.map((edu, idx) => (
              <div key={`edu-${idx}`} className="relative group">
                <div className="absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-blue-500 border-2 border-white shadow-sm" />
                <div className="flex items-baseline gap-2">
                  <GraduationCap className="w-4 h-4 text-blue-600 inline" />
                  <span className="font-semibold text-slate-900 text-sm">
                    {edu.degree || edu.level.toUpperCase()}
                  </span>
                  {edu.score_value && (
                    <span className="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {edu.score_value} {edu.score_scale || ''}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {edu.institution || edu.board_or_university || 'Institution not specified'}
                </p>
              </div>
            ))}

            {/* Internship items */}
            {internships.map((intn, idx) => (
              <div key={`int-${idx}`} className="relative group">
                <div className="absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-indigo-500 border-2 border-white shadow-sm" />
                <div className="flex items-baseline gap-2">
                  <Briefcase className="w-4 h-4 text-indigo-600 inline" />
                  <span className="font-semibold text-slate-900 text-sm">
                    {intn.role || 'Intern'} at {intn.company || 'Company'}
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">Internship</span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {intn.start_date || ''} {intn.end_date ? `— ${intn.end_date}` : '— Ongoing'}
                </p>
              </div>
            ))}

            {/* Job items */}
            {jobs.map((job, idx) => (
              <div key={`job-${idx}`} className="relative group">
                <div className="absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-white shadow-sm" />
                <div className="flex items-baseline gap-2">
                  <Briefcase className="w-4 h-4 text-emerald-600 inline" />
                  <span className="font-semibold text-slate-900 text-sm">
                    {job.role || 'Role'} at {job.company || 'Company'}
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">Full-time</span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {job.start_date || ''} {job.end_date ? `— ${job.end_date}` : '— Present'}
                </p>
              </div>
            ))}

            {education.length === 0 && internships.length === 0 && jobs.length === 0 && (
              <div className="text-sm text-slate-400 italic">
                No timeline records yet. Share your education and internship details in chat!
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
