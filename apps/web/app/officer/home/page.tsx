"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { API_BASE_URL } from "@/lib/supabase";
import { getCurrentSession, logout, UserSession } from "@/lib/auth";
import {
  getCollegeScore,
  listStudentRecords,
  toggleBatchShare,
  getBatchShares,
  importStudentRecords,
  draftLetter,
  listContacts,
  CampusScoreResponse,
  StudentListResponse,
  StudentCard,
  BatchShareResponse,
  ImportReport,
  LetterDraftResponse,
  ContactCard,
} from "@recruiting/shared";
import { ScoreBreakdownCard } from "@/components/ScoreBreakdownCard";
import { ConsentModal } from "@/components/ConsentModal";
import { DraftLetterModal } from "@/components/DraftLetterModal";
import {
  GraduationCap,
  MessageSquare,
  LogOut,
  Upload,
  Download,
  Search,
  CheckCircle2,
  XCircle,
  Share2,
  Loader2,
  Users,
  Mail,
  Building,
} from "lucide-react";

export default function PlacementOfficerHomePage() {
  const router = useRouter();

  const [session, setSession] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);

  // College Score state
  const [scoreData, setScoreData] = useState<CampusScoreResponse | null>(null);
  const [scoreLoading, setScoreLoading] = useState(false);

  // Batch shares state
  const [batchShares, setBatchShares] = useState<Record<number, boolean>>({
    2027: false,
    2028: false,
  });
  const [sharingLoading, setSharingLoading] = useState(false);

  // Student list & filter state
  const [students, setStudents] = useState<StudentCard[]>([]);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [totalStudents, setTotalStudents] = useState(0);
  const [studentsLoading, setStudentsLoading] = useState(false);

  // Filter values
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBatch, setSelectedBatch] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [selectedBranch, setSelectedBranch] = useState<string>("");

  // Modals state
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [selectedOutreachContact, setSelectedOutreachContact] =
    useState<ContactCard | null>(null);
  const [isDraftModalOpen, setIsDraftModalOpen] = useState(false);

  // Company outreach partners state
  const [companies, setCompanies] = useState<ContactCard[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(false);

  // Export loading
  const [isExporting, setIsExporting] = useState(false);

  // 1. Initial Authentication Check
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
        userSession.user.role !== "placement_officer" &&
        userSession.user.role !== "admin"
      ) {
        // Redirect non-officers to their proper home
        if (userSession.user.role === "student") router.replace("/home");
        else if (userSession.user.role === "company")
          router.replace("/company/home");
        else router.replace("/chat");
        return;
      }
      setSession(userSession);
      setLoading(false);
    });
  }, [router]);

  // 2. Fetch College Score
  const loadScore = useCallback(
    async (token: string, collegeId?: string | null) => {
      const targetId = collegeId || "default-college";
      setScoreLoading(true);
      try {
        const res = await getCollegeScore(API_BASE_URL, targetId, token);
        setScoreData(res);
      } catch (err: any) {
        console.error("Failed to load college score:", err);
      } finally {
        setScoreLoading(false);
      }
    },
    []
  );

  // 3. Fetch Batch Shares
  const loadBatchShares = useCallback(async (token: string) => {
    try {
      const res: BatchShareResponse[] = await getBatchShares(
        API_BASE_URL,
        token
      );
      const shareMap: Record<number, boolean> = { 2027: false, 2028: false };
      if (Array.isArray(res)) {
        res.forEach((item) => {
          shareMap[item.batch_year] = item.shared_with_recruiters;
        });
      }
      setBatchShares(shareMap);
    } catch (err: any) {
      console.error("Failed to load batch shares:", err);
    }
  }, []);

  // 4. Fetch Student Records
  const loadStudents = useCallback(
    async (token: string) => {
      setStudentsLoading(true);
      try {
        const params: any = { page_size: 100 };
        if (searchQuery.trim()) params.q = searchQuery.trim();
        if (selectedBatch) params.batch_year = parseInt(selectedBatch, 10);
        if (selectedStatus) params.status = selectedStatus;
        if (selectedBranch) params.branch = selectedBranch;

        const res: StudentListResponse = await listStudentRecords(
          API_BASE_URL,
          params,
          token
        );
        setStudents(res.items || []);
        setTotalStudents(res.total || 0);
        if (res.status_counts) {
          setStatusCounts(res.status_counts);
        }
      } catch (err: any) {
        console.error("Failed to load students:", err);
      } finally {
        setStudentsLoading(false);
      }
    },
    [searchQuery, selectedBatch, selectedStatus, selectedBranch]
  );

  // 5. Fetch Company Outreach Contacts
  const loadCompanyPartners = useCallback(async (token: string) => {
    setCompaniesLoading(true);
    try {
      const res = await listContacts(API_BASE_URL, token, {
        role_type: "recruiter",
        page_size: 20,
      });
      if (res && res.items) {
        setCompanies(res.items);
      }
    } catch (err: any) {
      console.error("Failed to load company partners:", err);
    } finally {
      setCompaniesLoading(false);
    }
  }, []);

  // Trigger loads once session is ready
  useEffect(() => {
    if (!session) return;
    loadScore(session.token, session.user.collegeId);
    loadBatchShares(session.token);
    loadStudents(session.token);
    loadCompanyPartners(session.token);
  }, [session, loadScore, loadBatchShares, loadStudents, loadCompanyPartners]);

  // Handle batch sharing toggle
  async function handleToggleShare(year: number) {
    if (!session || sharingLoading) return;
    setSharingLoading(true);
    const newShared = !batchShares[year];
    try {
      await toggleBatchShare(API_BASE_URL, year, newShared, session.token);
      setBatchShares((prev) => ({ ...prev, [year]: newShared }));
    } catch (err: any) {
      alert(err?.message || "Failed to update batch sharing");
    } finally {
      setSharingLoading(false);
    }
  }

  // Handle CSV export of filtered records
  async function handleExportFilteredCSV() {
    if (!session || isExporting) return;
    setIsExporting(true);
    try {
      const query = new URLSearchParams();
      if (searchQuery.trim()) query.set("q", searchQuery.trim());
      if (selectedBatch) query.set("batch_year", selectedBatch);
      if (selectedStatus) query.set("status", selectedStatus);
      if (selectedBranch) query.set("branch", selectedBranch);

      const res = await fetch(
        `${API_BASE_URL}/v1/student-records/export?${query.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${session.token}`,
          },
        }
      );

      if (!res.ok) {
        throw new Error("Failed to export student records");
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `student_records_batch_${selectedBatch || "all"}_export.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err?.message || "Export failed");
    } finally {
      setIsExporting(false);
    }
  }

  // Handle file import
  async function handleImport(file: File): Promise<ImportReport> {
    if (!session) throw new Error("Not authenticated");
    const result = await importStudentRecords(
      API_BASE_URL,
      file,
      session.token
    );
    // Reload score and students
    loadScore(session.token, session.user.collegeId);
    loadStudents(session.token);
    return result;
  }

  // Handle draft outreach letter
  async function handleGenerateDraft(
    kind: "invitation" | "interview" | "offer"
  ): Promise<LetterDraftResponse> {
    if (!session || !selectedOutreachContact) {
      throw new Error("Missing contact or session");
    }
    return await draftLetter(
      API_BASE_URL,
      {
        kind,
        contact_id: selectedOutreachContact.id,
        channel: "email",
        sender_context: `${session.user.displayName}, Placement Office`,
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
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-xs">
              <GraduationCap className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900">
                Placement Officer Portal
              </h1>
              <p className="text-xs text-slate-500">
                {session?.user.displayName || "Placement Director"} • Mumbai
                Region
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Link
              href="/chat"
              className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3.5 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition shadow-2xs"
            >
              <MessageSquare className="h-4 w-4" />
              <span>Campus Assistant</span>
            </Link>

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

      <main className="mx-auto max-w-7xl space-y-6 px-4 pt-6 sm:px-6">
        {/* Section 1: College Score & Breakdown */}
        {scoreLoading && !scoreData ? (
          <div className="flex h-44 items-center justify-center rounded-2xl border border-slate-200 bg-white">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
          </div>
        ) : scoreData ? (
          <ScoreBreakdownCard
            title="Campus Full-Time Score"
            score={scoreData.campus_score}
            subtitle="Campus placement readiness score"
            secondaryScore={{
              label: "Internship Score",
              score: scoreData.campus_internship_score,
            }}
            breakdown={scoreData.breakdown || []}
            nextActions={scoreData.next_best_actions || []}
            flagged={scoreData.flagged || []}
          />
        ) : (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-xs text-slate-500">
            No score data available yet. Import student records below.
          </div>
        )}

        {/* Section 2: Batch Sharing with Recruiters */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <div className="flex items-center gap-2.5 mb-2">
            <Share2 className="h-5 w-5 text-indigo-600" />
            <h2 className="text-base font-bold text-slate-900">
              Share Batches with Verified Recruiters
            </h2>
          </div>

          <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3.5 text-xs text-indigo-900 leading-relaxed mb-5">
            <span className="font-bold">Privacy Protection Rule: </span>
            When batch sharing is enabled, verified recruiters and companies can
            discover students in that batch who have not opted out. Aadhaar
            numbers, personal phone numbers, emails, and uploaded documents are
            strictly kept private and never shared.
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[2027, 2028].map((year) => {
              const isShared = Boolean(batchShares[year]);
              return (
                <div
                  key={year}
                  className="flex items-center justify-between rounded-xl border border-slate-200 p-4 bg-slate-50/50"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 text-sm">
                        Batch {year}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold border ${
                          isShared
                            ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                            : "bg-slate-200 text-slate-700 border-slate-300"
                        }`}
                      >
                        {isShared ? (
                          <>
                            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                            <span>Shared with Recruiters</span>
                          </>
                        ) : (
                          <>
                            <XCircle className="h-3 w-3 text-slate-500" />
                            <span>Not Shared (Private)</span>
                          </>
                        )}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500">
                      {year === 2027
                        ? "Graduating 2027 • Final placements & summer internships"
                        : "Graduating 2028 • Pre-final internships & discovery"}
                    </p>
                  </div>

                  <button
                    type="button"
                    disabled={sharingLoading}
                    onClick={() => handleToggleShare(year)}
                    className={`rounded-xl px-4 py-2 text-xs font-semibold transition shadow-2xs ${
                      isShared
                        ? "bg-white border border-slate-300 text-slate-700 hover:bg-slate-100"
                        : "bg-indigo-600 text-white hover:bg-indigo-700"
                    }`}
                  >
                    {isShared ? "Revoke Sharing" : "Share Batch"}
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        {/* Section 3: Student Roster & Filters */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-indigo-600" />
                <h2 className="text-base font-bold text-slate-900">
                  Student Records Roster
                </h2>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                  {totalStudents} students
                </span>
              </div>
              <p className="mt-0.5 text-xs text-slate-500">
                Manage batch rosters, track placement readiness, and export
                views.
              </p>
            </div>

            {/* Action Buttons: Import & Export */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setIsImportModalOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-700 transition shadow-xs"
              >
                <Upload className="h-3.5 w-3.5" />
                <span>Import Student CSV</span>
              </button>

              <button
                type="button"
                disabled={isExporting}
                onClick={handleExportFilteredCSV}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition shadow-2xs disabled:opacity-50"
              >
                {isExporting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5 text-slate-500" />
                )}
                <span>Export CSV</span>
              </button>
            </div>
          </div>

          {/* Status Counts Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              {
                key: "in_college",
                label: "In College",
                color: "bg-blue-50 text-blue-800 border-blue-200",
              },
              {
                key: "internship",
                label: "Internship Secured",
                color: "bg-emerald-50 text-emerald-800 border-emerald-200",
              },
              {
                key: "full_time",
                label: "Full-Time Placed",
                color: "bg-purple-50 text-purple-800 border-purple-200",
              },
              {
                key: "not_placed",
                label: "Seeking Placement",
                color: "bg-amber-50 text-amber-800 border-amber-200",
              },
            ].map((st) => (
              <div
                key={st.key}
                className={`rounded-xl border p-3 ${st.color} flex flex-col justify-between`}
              >
                <span className="text-[11px] font-semibold uppercase tracking-wider">
                  {st.label}
                </span>
                <span className="text-2xl font-extrabold mt-1">
                  {statusCounts[st.key] || 0}
                </span>
              </div>
            ))}
          </div>

          {/* Filter Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 pt-2">
            <div className="sm:col-span-5 relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by student name or roll number..."
                className="w-full rounded-xl border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              />
            </div>

            <div className="sm:col-span-2">
              <select
                value={selectedBatch}
                onChange={(e) => setSelectedBatch(e.target.value)}
                className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              >
                <option value="">All Batches</option>
                <option value="2027">Batch 2027</option>
                <option value="2028">Batch 2028</option>
              </select>
            </div>

            <div className="sm:col-span-2">
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
              >
                <option value="">All Statuses</option>
                <option value="in_college">In College</option>
                <option value="internship">Internship</option>
                <option value="full_time">Full Time</option>
                <option value="not_placed">Seeking Placement</option>
              </select>
            </div>

            <div className="sm:col-span-3">
              <select
                value={selectedBranch}
                onChange={(e) => setSelectedBranch(e.target.value)}
                className="w-full rounded-xl border border-slate-300 py-2 px-3 text-xs text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
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
                <option value="Civil Engineering">Civil Engineering</option>
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            {studentsLoading ? (
              <div className="flex h-44 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
              </div>
            ) : students.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                <Users className="mx-auto h-8 w-8 text-slate-300 mb-2" />
                <p className="font-semibold text-slate-700">
                  No student records found
                </p>
                <p className="mt-1">
                  Try adjusting filters or click &ldquo;Import Student
                  CSV&rdquo; to upload records.
                </p>
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-600 border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4">Student Name</th>
                    <th className="py-3 px-4">Batch</th>
                    <th className="py-3 px-4">Branch & Degree</th>
                    <th className="py-3 px-4">Score / CGPA</th>
                    <th className="py-3 px-4">Readiness Score</th>
                    <th className="py-3 px-4">Placement Status</th>
                    <th className="py-3 px-4">Batch Sharing</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {students.map((student: any) => {
                    const isOptedOut = student.opted_out === true;
                    return (
                      <tr
                        key={student.id}
                        className="hover:bg-slate-50/80 transition"
                      >
                        <td className="py-3 px-4 font-semibold text-slate-900">
                          {student.full_name}
                          {student.roll_number && (
                            <span className="block text-[11px] font-normal text-slate-400">
                              Roll: {student.roll_number}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono font-medium text-slate-700">
                            {student.batch_year}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-600">
                          {student.degree || "B.Tech"} •{" "}
                          {student.branch || "General"}
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-medium text-slate-800">
                            {student.score_value
                              ? `${student.score_value} ${student.score_scale || ""}`
                              : "—"}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          {student.student_score ? (
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-indigo-600">
                                {student.student_score}
                              </span>
                              <div className="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                                <div
                                  className="bg-indigo-600 h-1.5 rounded-full"
                                  style={{
                                    width: `${Math.min(
                                      100,
                                      Math.max(0, student.student_score)
                                    )}%`,
                                  }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-slate-400 text-[11px]">
                              Unrated
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold capitalize ${
                              student.current_status === "internship" ||
                              student.current_status === "full_time"
                                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                                : "bg-blue-50 text-blue-800 border border-blue-200"
                            }`}
                          >
                            {student.current_status?.replace("_", " ") ||
                              "In College"}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-medium border ${
                              isOptedOut
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : "bg-emerald-50 text-emerald-800 border-emerald-200"
                            }`}
                          >
                            {isOptedOut
                              ? "Student Opted Out"
                              : "Active in Batch"}
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

        {/* Section 4: Company Outreach & Draft Invitations */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2">
            <Building className="h-5 w-5 text-indigo-600" />
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Company Outreach & Placement Invitations
              </h2>
              <p className="text-xs text-slate-500">
                Invite recruiting partners to visit your campus for 2027/2028
                drives.
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-3 text-xs text-amber-900">
            <span className="font-bold">No Auto-Send Guarantee: </span>
            Clicking &ldquo;Draft Invitation&rdquo; generates an editable
            invitation letter. Nothing is ever sent automatically on your
            behalf.
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {companiesLoading ? (
              <div className="col-span-full py-8 text-center">
                <Loader2 className="mx-auto h-6 w-6 animate-spin text-indigo-600" />
              </div>
            ) : companies.length === 0 ? (
              <div className="col-span-full py-6 text-center text-xs text-slate-500">
                No recruiter contacts found in the Mumbai directory.
              </div>
            ) : (
              companies.map((comp) => (
                <div
                  key={comp.id}
                  className="flex flex-col justify-between rounded-xl border border-slate-200 p-4 bg-slate-50/40"
                >
                  <div>
                    <h3 className="font-bold text-slate-900 text-xs">
                      {comp.name}
                    </h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {comp.title || "Recruiter"} •{" "}
                      {comp.company_name || "Enterprise"}
                    </p>
                    {comp.location && (
                      <p className="text-[10px] text-slate-400 mt-1">
                        📍 {comp.location}
                      </p>
                    )}
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[10px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      Active Partner
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedOutreachContact(comp);
                        setIsDraftModalOpen(true);
                      }}
                      className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-indigo-700 transition"
                    >
                      <Mail className="h-3 w-3" />
                      <span>Draft Invitation</span>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      {/* CSV Import Modal with Consent & Privacy Sheet */}
      <ConsentModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        title="Import Student Records (CSV)"
        description="Upload your official student enrollment roster for batches 2027 and 2028. The system deterministically maps student identifiers, academic standing, and readiness."
        privacyNotice="Student records are strictly protected. Sensitive identity attributes (Aadhaar numbers, personal phone numbers, and emails) are stored under college protection rules and never disclosed to employers or external callers."
        templateUrl={`${API_BASE_URL}/v1/student-records/template`}
        templateFilename="student_records_template.csv"
        onUpload={handleImport}
      />

      {/* Draft Letter Modal */}
      {selectedOutreachContact && (
        <DraftLetterModal
          isOpen={isDraftModalOpen}
          onClose={() => {
            setIsDraftModalOpen(false);
            setSelectedOutreachContact(null);
          }}
          recipientName={selectedOutreachContact.name}
          recipientRole={selectedOutreachContact.title || "Campus Recruiter"}
          recipientEmail={selectedOutreachContact.email}
          defaultKind="invitation"
          onGenerateDraft={handleGenerateDraft}
        />
      )}
    </div>
  );
}
