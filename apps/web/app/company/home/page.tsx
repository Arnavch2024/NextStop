"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/supabase";
import { getCurrentSession, logout, UserSession } from "@/lib/auth";
import {
  getCompanyScore,
  listCampusHiring,
  importCampusHiring,
  listStudentRecords,
  listContacts,
  draftLetter,
  CompanyScoreResponse,
  CampusHiringRecord,
  StudentCard,
  StudentListResponse,
  ImportReport,
  LetterDraftResponse,
  ContactCard,
} from "@recruiting/shared";
import { ScoreBreakdownCard } from "@/components/ScoreBreakdownCard";
import { ConsentModal } from "@/components/ConsentModal";
import { DraftLetterModal } from "@/components/DraftLetterModal";
import { SwitchDemoRoleButton } from "@/app/components/SwitchDemoRoleButton";
import {
  Building2,
  MessageSquare,
  LogOut,
  Upload,
  Search,
  Loader2,
  Users,
  GraduationCap,
  Briefcase,
  Mail,
  Award,
  Layers,
  ShieldCheck,
} from "lucide-react";

export default function CompanyHomePage() {
  const router = useRouter();

  const [session, setSession] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"hiring" | "students">("hiring");

  // Company Score state
  const [scoreData, setScoreData] = useState<CompanyScoreResponse | null>(null);
  const [scoreLoading, setScoreLoading] = useState(false);

  // Campus Hiring state
  const [hiringRecords, setHiringRecords] = useState<CampusHiringRecord[]>([]);
  const [hiringLoading, setHiringLoading] = useState(false);
  const [selectedCycleYear, setSelectedCycleYear] = useState<string>("");
  const [selectedHiringType, setSelectedHiringType] = useState<string>("");

  // Student Search state
  const [students, setStudents] = useState<StudentCard[]>([]);
  const [studentsTotal, setStudentsTotal] = useState(0);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBatch, setSelectedBatch] = useState<string>("");
  const [selectedBranch, setSelectedBranch] = useState<string>("");
  const [minScore, setMinScore] = useState<string>("");

  // College Outreach Tracker state
  const [collegeOfficers, setCollegeOfficers] = useState<ContactCard[]>([]);
  const [officersLoading, setOfficersLoading] = useState(false);

  // Modals state
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [draftRecipient, setDraftRecipient] = useState<{
    id: string;
    name: string;
    role?: string;
    email?: string | null;
    defaultKind: "invitation" | "interview" | "offer";
  } | null>(null);
  const [isDraftModalOpen, setIsDraftModalOpen] = useState(false);

  // 1. Authenticate user
  useEffect(() => {
    getCurrentSession().then((userSession) => {
      if (!userSession) {
        router.replace("/login");
        return;
      }
      if (!userSession.user.role) {
        router.replace("/onboarding");
        return;
      }
      if (
        userSession.user.role !== "company" &&
        userSession.user.role !== "admin"
      ) {
        if (userSession.user.role === "student") router.replace("/home");
        else if (userSession.user.role === "placement_officer")
          router.replace("/officer/home");
        else router.replace("/chat");
        return;
      }
      setSession(userSession);
      setLoading(false);
    });
  }, [router]);

  // 2. Load Company Score
  const loadScore = useCallback(
    async (token: string, companyId?: string | null) => {
      const targetId = companyId || "default-company";
      setScoreLoading(true);
      try {
        const res = await getCompanyScore(API_BASE_URL, targetId, token);
        setScoreData(res);
      } catch (err: any) {
        console.error("Failed to load company score:", err);
      } finally {
        setScoreLoading(false);
      }
    },
    []
  );

  // 3. Load Campus Hiring Records
  const loadCampusHiring = useCallback(
    async (token: string) => {
      setHiringLoading(true);
      try {
        const params: any = {};
        if (selectedCycleYear)
          params.cycle_year = parseInt(selectedCycleYear, 10);
        if (selectedHiringType) params.type = selectedHiringType;
        const res = await listCampusHiring(API_BASE_URL, params, token);
        setHiringRecords(Array.isArray(res) ? res : []);
      } catch (err: any) {
        console.error("Failed to load campus hiring:", err);
      } finally {
        setHiringLoading(false);
      }
    },
    [selectedCycleYear, selectedHiringType]
  );

  // 4. Load College Officers for outreach tracker
  const loadCollegeOfficers = useCallback(async (token: string) => {
    setOfficersLoading(true);
    try {
      const res = await listContacts(API_BASE_URL, token, {
        role_type: "officer",
        page_size: 20,
      });
      if (res && res.items) {
        setCollegeOfficers(res.items);
      }
    } catch (err: any) {
      console.error("Failed to load college officers:", err);
    } finally {
      setOfficersLoading(false);
    }
  }, []);

  // 5. Load Students (minimal fields only)
  const loadStudents = useCallback(
    async (token: string) => {
      setStudentsLoading(true);
      try {
        const params: any = { page_size: 30 };
        if (searchQuery.trim()) params.q = searchQuery.trim();
        if (selectedBatch) params.batch_year = parseInt(selectedBatch, 10);
        if (selectedBranch) params.branch = selectedBranch;
        if (minScore) params.min_score = parseFloat(minScore);

        const res: StudentListResponse = await listStudentRecords(
          API_BASE_URL,
          params,
          token
        );
        setStudents(res.items || []);
        setStudentsTotal(res.total || 0);
      } catch (err: any) {
        console.error("Failed to load students:", err);
      } finally {
        setStudentsLoading(false);
      }
    },
    [searchQuery, selectedBatch, selectedBranch, minScore]
  );

  // Initial trigger
  useEffect(() => {
    if (!session) return;
    loadScore(session.token, session.user.companyId);
    loadCampusHiring(session.token);
    loadCollegeOfficers(session.token);
    loadStudents(session.token);
  }, [session, loadScore, loadCampusHiring, loadCollegeOfficers, loadStudents]);

  // Handle CSV import for hiring history
  async function handleImportHiring(file: File): Promise<ImportReport> {
    if (!session) throw new Error("Not authenticated");
    const result = await importCampusHiring(API_BASE_URL, file, session.token);
    loadScore(session.token, session.user.companyId);
    loadCampusHiring(session.token);
    return result;
  }

  // Handle draft letter generation
  async function handleGenerateDraft(
    kind: "invitation" | "interview" | "offer"
  ): Promise<LetterDraftResponse> {
    if (!session || !draftRecipient) {
      throw new Error("Missing recipient or session");
    }
    return await draftLetter(
      API_BASE_URL,
      {
        kind,
        contact_id: draftRecipient.id,
        channel: "email",
        sender_context: `${session.user.displayName}, Campus Talent Team`,
      },
      session.token
    );
  }

  async function handleSignOut() {
    await logout();
    router.replace("/login");
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 pb-12">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur-xs">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs">
              <Building2 className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900">
                Company Hiring Portal
              </h1>
              <p className="text-xs text-slate-500">
                {session?.user.displayName || "Tech Recruiting Partner"} •
                Mumbai Campus Talent
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Link
              href="/chat"
              className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3.5 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100 transition shadow-2xs"
            >
              <MessageSquare className="h-4 w-4" />
              <span>Talent Assistant</span>
            </Link>

            {session?.user.isDemo && <SwitchDemoRoleButton />}

            <button
              type="button"
              onClick={handleSignOut}
              className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Tabs Navigation */}
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 flex gap-6">
          <button
            type="button"
            onClick={() => setActiveTab("hiring")}
            className={`py-3.5 text-xs font-bold border-b-2 transition flex items-center gap-2 ${
              activeTab === "hiring"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Layers className="h-4 w-4" />
            <span>Campus Hiring & Company Score</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("students")}
            className={`py-3.5 text-xs font-bold border-b-2 transition flex items-center gap-2 ${
              activeTab === "students"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Users className="h-4 w-4" />
            <span>Student Search & Discovery</span>
            {studentsTotal > 0 && (
              <span className="rounded-full bg-blue-100 px-2 py-0.2 text-[10px] font-bold text-blue-700">
                {studentsTotal}
              </span>
            )}
          </button>
        </div>
      </div>

      <main className="mx-auto max-w-7xl space-y-6 px-4 pt-6 sm:px-6">
        {/* TAB 1: Campus Hiring & Company Score */}
        {activeTab === "hiring" && (
          <div className="space-y-6">
            {/* 1. Company Score Breakdown Card */}
            {scoreLoading && !scoreData ? (
              <div className="flex h-44 items-center justify-center rounded-2xl border border-slate-200 bg-white">
                <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
              </div>
            ) : scoreData ? (
              <ScoreBreakdownCard
                title="Company Talent Score"
                score={scoreData.score}
                subtitle="Mumbai campus hiring effectiveness score"
                breakdown={scoreData.breakdown || []}
                nextActions={scoreData.next_best_actions || []}
              />
            ) : (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-xs text-slate-500">
                No company score calculated yet. Import hiring history below.
              </div>
            )}

            {/* 2. Campus Hiring Table */}
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <GraduationCap className="h-5 w-5 text-blue-600" />
                    <h2 className="text-base font-bold text-slate-900">
                      Campus Hiring History by Cycle
                    </h2>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Track colleges visited, interview volumes, and offer
                    acceptance by year.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setIsImportModalOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-blue-700 transition shadow-xs"
                >
                  <Upload className="h-3.5 w-3.5" />
                  <span>Import Hiring CSV</span>
                </button>
              </div>

              {/* Filters */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <select
                  value={selectedCycleYear}
                  onChange={(e) => setSelectedCycleYear(e.target.value)}
                  className="rounded-xl border border-slate-300 py-1.5 px-3 text-xs text-slate-800 focus:border-blue-600 focus:outline-none"
                >
                  <option value="">All Cycle Years</option>
                  <option value="2026">2026 Cycle</option>
                  <option value="2025">2025 Cycle</option>
                  <option value="2024">2024 Cycle</option>
                </select>

                <select
                  value={selectedHiringType}
                  onChange={(e) => setSelectedHiringType(e.target.value)}
                  className="rounded-xl border border-slate-300 py-1.5 px-3 text-xs text-slate-800 focus:border-blue-600 focus:outline-none"
                >
                  <option value="">All Hiring Types</option>
                  <option value="final">Final Placement</option>
                  <option value="internship">Summer Internship</option>
                </select>
              </div>

              {/* Table */}
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                {hiringLoading ? (
                  <div className="flex h-36 items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                  </div>
                ) : hiringRecords.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    <GraduationCap className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                    <p className="font-semibold text-slate-700">
                      No campus hiring records
                    </p>
                    <p className="mt-1">
                      Upload your previous season records via &ldquo;Import
                      Hiring CSV&rdquo;.
                    </p>
                  </div>
                ) : (
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-600 border-b border-slate-200">
                      <tr>
                        <th className="py-3 px-4">College Visited</th>
                        <th className="py-3 px-4">Cycle Year</th>
                        <th className="py-3 px-4">Drive Type</th>
                        <th className="py-3 px-4">Students Interviewed</th>
                        <th className="py-3 px-4">Offers Made</th>
                        <th className="py-3 px-4">Yield Rate</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {hiringRecords.map((rec) => {
                        const yieldRate =
                          rec.students_interviewed > 0
                            ? Math.round(
                                (rec.offers_made / rec.students_interviewed) *
                                  100
                              )
                            : 0;
                        return (
                          <tr
                            key={rec.id}
                            className="hover:bg-slate-50/80 transition"
                          >
                            <td className="py-3 px-4 font-semibold text-slate-900">
                              {rec.college_name || "Mumbai Engineering College"}
                            </td>
                            <td className="py-3 px-4 font-mono font-medium text-slate-700">
                              {rec.cycle_year}
                            </td>
                            <td className="py-3 px-4">
                              <span className="inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 capitalize">
                                {rec.type}
                              </span>
                            </td>
                            <td className="py-3 px-4 font-bold text-slate-800">
                              {rec.students_interviewed}
                            </td>
                            <td className="py-3 px-4 font-bold text-emerald-600">
                              {rec.offers_made}
                            </td>
                            <td className="py-3 px-4">
                              <span className="font-mono text-xs text-slate-700 font-semibold">
                                {yieldRate}%
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </section>

            {/* 3. College Outreach Tracker */}
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
              <div className="flex items-center gap-2">
                <Briefcase className="h-5 w-5 text-blue-600" />
                <div>
                  <h2 className="text-base font-bold text-slate-900">
                    College Placement Officers Tracker
                  </h2>
                  <p className="text-xs text-slate-500">
                    Connect with placement cells across VJTI, SPIT, DJ Sanghvi,
                    and Mumbai institutes.
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3 text-xs text-amber-900">
                <span className="font-bold">No Auto-Send Guarantee: </span>
                Clicking &ldquo;Draft Outreach&rdquo; prepares an editable
                collaboration letter. Nothing is sent automatically.
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {officersLoading ? (
                  <div className="col-span-full py-8 text-center">
                    <Loader2 className="mx-auto h-6 w-6 animate-spin text-blue-600" />
                  </div>
                ) : collegeOfficers.length === 0 ? (
                  <div className="col-span-full py-6 text-center text-xs text-slate-500">
                    No college placement officers found in directory.
                  </div>
                ) : (
                  collegeOfficers.map((officer) => (
                    <div
                      key={officer.id}
                      className="flex flex-col justify-between rounded-xl border border-slate-200 p-4 bg-slate-50/40"
                    >
                      <div>
                        <h3 className="font-bold text-slate-900 text-xs">
                          {officer.name}
                        </h3>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          {officer.title || "Placement Officer"} •{" "}
                          {officer.college_name || "Engineering Institute"}
                        </p>
                        {officer.location && (
                          <p className="text-[10px] text-slate-400 mt-1">
                            📍 {officer.location}
                          </p>
                        )}
                      </div>

                      <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-[10px] font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                          Placement Cell
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setDraftRecipient({
                              id: officer.id,
                              name: officer.name,
                              role: officer.title || "Placement Officer",
                              email: officer.email,
                              defaultKind: "invitation",
                            });
                            setIsDraftModalOpen(true);
                          }}
                          className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-blue-700 transition"
                        >
                          <Mail className="h-3 w-3" />
                          <span>Draft Outreach</span>
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>
        )}

        {/* TAB 2: Student Search & Discovery */}
        {activeTab === "students" && (
          <div className="space-y-6">
            {/* Search and Filters Bar */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Mumbai Campus Talent Discovery (Batches 2027 & 2028)
                </h2>
                <p className="text-xs text-slate-500">
                  Search shared batches from partnered Mumbai engineering
                  colleges.
                </p>
              </div>

              {/* Strict Privacy Protection Rule */}
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5 flex items-start gap-2.5">
                <ShieldCheck className="h-5 w-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-emerald-950 leading-relaxed">
                  <span className="font-bold">Student Privacy Enforced: </span>
                  Student contact information (Aadhaar number, personal phone
                  number, email address, and uploaded resumes) is strictly
                  private and never shared with employers or recruiters. Only
                  authorized placement records and scores are visible.
                </div>
              </div>

              {/* Filter controls */}
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 pt-1">
                <div className="sm:col-span-4 relative">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search candidate name or college..."
                    className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-600"
                  />
                </div>

                <div className="sm:col-span-2">
                  <select
                    value={selectedBatch}
                    onChange={(e) => setSelectedBatch(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs text-slate-900 focus:border-blue-600 focus:outline-none"
                  >
                    <option value="">All Batches</option>
                    <option value="2027">Batch 2027</option>
                    <option value="2028">Batch 2028</option>
                  </select>
                </div>

                <div className="sm:col-span-3">
                  <select
                    value={selectedBranch}
                    onChange={(e) => setSelectedBranch(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs text-slate-900 focus:border-blue-600 focus:outline-none"
                  >
                    <option value="">All Branches</option>
                    <option value="Computer Engineering">
                      Computer Engineering
                    </option>
                    <option value="Information Technology">
                      Information Technology
                    </option>
                    <option value="Electronics & Telecomm">
                      Electronics & Telecomm
                    </option>
                    <option value="Mechanical Engineering">
                      Mechanical Engineering
                    </option>
                  </select>
                </div>

                <div className="sm:col-span-3">
                  <select
                    value={minScore}
                    onChange={(e) => setMinScore(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs text-slate-900 focus:border-blue-600 focus:outline-none"
                  >
                    <option value="">Any Readiness Score</option>
                    <option value="70">Score 70+ / 100</option>
                    <option value="80">Score 80+ / 100</option>
                    <option value="90">Score 90+ / 100</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Student Results Cards */}
            {studentsLoading ? (
              <div className="flex h-56 items-center justify-center rounded-2xl border border-slate-200 bg-white">
                <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
              </div>
            ) : students.length === 0 ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center text-xs text-slate-500">
                <Users className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                <p className="font-semibold text-slate-700 text-sm">
                  No discoverable students match
                </p>
                <p className="mt-1 text-slate-500">
                  Only students in batches shared by their college and who have
                  not opted out are visible.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {students.map((student) => {
                  const studentScore = student.student_score ?? 75;
                  const isUnverified = student.unverified !== false;

                  return (
                    <div
                      key={student.id}
                      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs flex flex-col justify-between hover:border-blue-300 hover:shadow-sm transition"
                    >
                      <div>
                        {/* Header: Name + Badge */}
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h3 className="font-bold text-slate-900 text-sm">
                              {student.full_name}
                            </h3>
                            <p className="text-xs text-blue-700 font-medium mt-0.5">
                              {student.college_name ||
                                "Mumbai Engineering College"}
                            </p>
                          </div>
                          <span
                            className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-medium border ${
                              isUnverified
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : "bg-emerald-50 text-emerald-800 border-emerald-200"
                            }`}
                          >
                            {isUnverified
                              ? "Unverified, check the source"
                              : "Verified"}
                          </span>
                        </div>

                        {/* Details Grid (Minimal Visible Fields Only) */}
                        <div className="mt-3.5 space-y-1.5 text-xs text-slate-600">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">Batch Year:</span>
                            <span className="font-semibold text-slate-800 font-mono">
                              Batch {student.batch_year}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">
                              Degree & Branch:
                            </span>
                            <span className="font-medium text-slate-800 truncate max-w-[180px]">
                              {student.degree || "B.Tech"} •{" "}
                              {student.branch || "General"}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">
                              Academic Standing:
                            </span>
                            <span className="font-medium text-slate-800">
                              {student.score_value
                                ? `${student.score_value} ${student.score_scale || ""}`
                                : "Good Standing"}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-slate-400">
                              Current Status:
                            </span>
                            <span className="inline-flex items-center rounded-md px-2 py-0.2 text-[10px] font-medium bg-slate-100 text-slate-700 capitalize">
                              {student.current_status?.replace("_", " ") ||
                                "In College"}
                            </span>
                          </div>
                        </div>

                        {/* Readiness Score Bar */}
                        <div className="mt-4 pt-3 border-t border-slate-100">
                          <div className="flex items-center justify-between text-xs mb-1">
                            <span className="font-semibold text-slate-600 flex items-center gap-1">
                              <Award className="h-3.5 w-3.5 text-amber-500" />
                              <span>Student Readiness Score</span>
                            </span>
                            <span className="font-bold text-blue-600">
                              {studentScore} / 100
                            </span>
                          </div>
                          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-blue-600 h-1.5 rounded-full"
                              style={{
                                width: `${Math.min(100, Math.max(0, studentScore))}%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Actions: Draft Interview / Offer Letter */}
                      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setDraftRecipient({
                              id: student.id,
                              name: student.full_name,
                              role: `Candidate • Batch ${student.batch_year}`,
                              email: null, // Minimal fields: email is never exposed
                              defaultKind: "interview",
                            });
                            setIsDraftModalOpen(true);
                          }}
                          className="flex-1 inline-flex items-center justify-center gap-1 rounded-xl bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 transition shadow-2xs"
                        >
                          <Mail className="h-3.5 w-3.5" />
                          <span>Interview Invite</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setDraftRecipient({
                              id: student.id,
                              name: student.full_name,
                              role: `Candidate • Batch ${student.batch_year}`,
                              email: null,
                              defaultKind: "offer",
                            });
                            setIsDraftModalOpen(true);
                          }}
                          className="inline-flex items-center justify-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition shadow-2xs"
                        >
                          <span>Offer Letter</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Campus Hiring CSV Import Modal */}
      <ConsentModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        title="Import Campus Hiring History (CSV)"
        description="Upload your campus recruitment history from past seasons (colleges visited, cycle year, students interviewed, and offers made)."
        privacyNotice="Hiring data is processed to update your institutional talent performance and company readiness score. File cells are strictly treated as data and never instructions."
        onUpload={handleImportHiring}
      />

      {/* Draft Letter Modal */}
      {draftRecipient && (
        <DraftLetterModal
          isOpen={isDraftModalOpen}
          onClose={() => {
            setIsDraftModalOpen(false);
            setDraftRecipient(null);
          }}
          recipientName={draftRecipient.name}
          recipientRole={draftRecipient.role}
          recipientEmail={draftRecipient.email}
          defaultKind={draftRecipient.defaultKind}
          onGenerateDraft={handleGenerateDraft}
        />
      )}
    </div>
  );
}
