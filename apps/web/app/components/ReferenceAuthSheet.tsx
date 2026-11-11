"use client";

import React, { useState } from "react";
import {
  authorizeReferenceCheck,
  revokeReferenceCheck,
  InternshipRecord,
  ScoreResponse,
} from "@recruiting/shared";
import {
  Award,
  Briefcase,
  X,
  CheckCircle2,
  Trash2,
  Loader2,
  Building,
  Info,
} from "lucide-react";

interface ReferenceAuthSheetProps {
  isOpen: boolean;
  onClose: () => void;
  token: string;
  baseUrl: string;
  internships: InternshipRecord[];
  isAuthorized: boolean;
  authorizedParty?: string | null;
  onSuccess: (score?: ScoreResponse, isAuthorized?: boolean) => void;
}

export function ReferenceAuthSheet({
  isOpen,
  onClose,
  token,
  baseUrl,
  internships = [],
  isAuthorized,
  authorizedParty,
  onSuccess,
}: ReferenceAuthSheetProps) {
  const [selectedInternshipId, setSelectedInternshipId] = useState<string>(
    internships[0]?.id || ""
  );
  const [selectedPartyType, setSelectedPartyType] = useState<string>(
    "Campus Placement Cell"
  );
  const [customPartyName, setCustomPartyName] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const partyName =
    selectedPartyType === "Other"
      ? customPartyName.trim() || "Verified Recruiter"
      : selectedPartyType;

  async function handleAuthorize() {
    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const selectedIntern = internships.find(
        (i) => i.id === selectedInternshipId
      );
      const res = await authorizeReferenceCheck(baseUrl, token, {
        internship_id: selectedInternshipId || undefined,
        authorized_party: partyName,
        authorized_role: selectedIntern?.role || "Intern",
      });

      setSuccessMessage(
        "Reference check authorized! +2 points added to score."
      );
      onSuccess(res.score, true);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || "Failed to authorize reference check.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRevoke() {
    if (
      !confirm(
        "Revoking authorization will remove reference outreach permission and decrease your readiness score by 2 points. Continue?"
      )
    ) {
      return;
    }

    setIsRevoking(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await revokeReferenceCheck(baseUrl, token);
      setSuccessMessage(
        "Reference authorization revoked. Readiness score updated."
      );
      onSuccess(res.score, false);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err.message || "Failed to revoke reference authorization.");
    } finally {
      setIsRevoking(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="max-w-lg w-full bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 my-8 animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Reference Check Authorization
              </h3>
              <p className="text-xs text-slate-500">
                Authorize recruiters & officers for +2 readiness points
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Informative description banner */}
        <div className="mt-4 rounded-xl bg-blue-50/80 border border-blue-200 p-3.5 flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <p className="text-xs text-blue-900 leading-relaxed">
            Authorizing lets verified recruiters, companies, and college
            placement cells contact your internship company to confirm your
            tenure and performance.
          </p>
        </div>

        {/* Authorized parties list with Revoke button */}
        {isAuthorized && (
          <div className="mt-4 p-4 rounded-xl border border-emerald-200 bg-emerald-50/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold text-emerald-950">
                  Active Reference Authorization
                </span>
              </div>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800">
                +2 pts active
              </span>
            </div>

            <div className="mt-3 bg-white p-3 rounded-lg border border-emerald-100 flex items-center justify-between text-xs">
              <div>
                <p className="font-bold text-slate-800">
                  {authorizedParty || "Campus Placement & Verified Recruiters"}
                </p>
                <p className="text-[11px] text-slate-500">
                  Permitted to generate reference outreach drafts
                </p>
              </div>
              <button
                type="button"
                onClick={handleRevoke}
                disabled={isRevoking}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg font-semibold text-xs transition disabled:opacity-50"
              >
                {isRevoking ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                <span>Revoke</span>
              </button>
            </div>
          </div>
        )}

        {/* Authorization Form */}
        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Select Associated Internship
            </label>
            {internships.length > 0 ? (
              <select
                value={selectedInternshipId}
                onChange={(e) => setSelectedInternshipId(e.target.value)}
                className="w-full text-xs font-medium border border-slate-200 rounded-xl px-3 py-2.5 bg-slate-50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                {internships.map((intn) => (
                  <option key={intn.id} value={intn.id}>
                    {intn.company || "Internship"} — {intn.role || "Intern"}
                  </option>
                ))}
              </select>
            ) : (
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-500 flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-slate-400 shrink-0" />
                <span>
                  No internship records found yet. You can still authorize for
                  general campus placement.
                </span>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Choose Authorized Party
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                "Campus Placement Cell",
                "Hiring Companies",
                "Verified Recruiters",
                "Other",
              ].map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setSelectedPartyType(p)}
                  className={`py-2 px-3 rounded-lg text-xs font-semibold border text-center transition ${
                    selectedPartyType === p
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700 shadow-xs"
                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>

            {selectedPartyType === "Other" && (
              <div className="mt-2.5">
                <input
                  type="text"
                  placeholder="Enter organization or company name"
                  value={customPartyName}
                  onChange={(e) => setCustomPartyName(e.target.value)}
                  className="w-full text-xs border border-slate-200 rounded-xl px-3 py-2 bg-white focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            )}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
            {error}
          </div>
        )}

        {/* Success message */}
        {successMessage && (
          <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 font-bold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Footer actions */}
        <div className="mt-6 flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={handleAuthorize}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
          >
            {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>Authorize Reference Check (+2 pts)</span>
          </button>
        </div>
      </div>
    </div>
  );
}
