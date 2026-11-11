"use client";

import React, { useState } from "react";
import {
  ConfirmationCard,
  verifyMock,
  authorizeReferenceCheck,
  revokeReferenceCheck,
  ScoreResponse,
} from "@recruiting/shared";
import {
  ShieldCheck,
  Award,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";

interface ChatConfirmationCardProps {
  card: ConfirmationCard;
  token: string;
  baseUrl: string;
  onSuccess?: (score?: ScoreResponse, message?: string) => void;
  onOpenUpload?: () => void;
}

export function ChatConfirmationCard({
  card,
  token,
  baseUrl,
  onSuccess,
  onOpenUpload,
}: ChatConfirmationCardProps) {
  const [status, setStatus] = useState<
    "idle" | "loading" | "confirmed" | "cancelled" | "error"
  >("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const isVerify =
    card.action === "verify_mock" || card.type === "verify_mock_confirmation";
  const isAuth =
    card.action === "authorize_reference_check" ||
    card.type === "reference_check_confirmation";
  const isRevoke =
    card.action === "revoke_reference_check" ||
    card.type === "revoke_reference_check_confirmation";

  async function handleConfirm() {
    setStatus("loading");
    setErrorMessage(null);

    try {
      if (isVerify) {
        try {
          const res = await verifyMock(baseUrl, token, {
            document_type: card.document_type || "aadhaar",
          });
          setStatus("confirmed");
          setFeedback(
            `Sample document pre-verified! +2 points added. Status: ${res.verification_note || "Demo verification (mocked)"}`
          );
          if (onSuccess)
            onSuccess(res.score, "Document pre-verified (+2 points)");
        } catch (err: any) {
          if (
            err.status === 404 &&
            err.message?.includes("No document found")
          ) {
            setStatus("error");
            setErrorMessage(
              "No sample document uploaded yet. Please upload a sample file first."
            );
            if (onOpenUpload) onOpenUpload();
          } else if (err.status === 404) {
            setStatus("error");
            setErrorMessage("Verification is not enabled in this environment.");
          } else {
            setStatus("error");
            setErrorMessage(err.message || "Failed to verify document.");
          }
        }
      } else if (isAuth) {
        const res = await authorizeReferenceCheck(baseUrl, token, {
          authorized_party: card.company || "Campus Placement Cell",
          authorized_role: "Intern",
        });
        setStatus("confirmed");
        setFeedback(
          "Reference check authorized! +2 points added to readiness score."
        );
        if (onSuccess)
          onSuccess(res.score, "Reference check authorized (+2 points)");
      } else if (isRevoke) {
        const res = await revokeReferenceCheck(baseUrl, token);
        setStatus("confirmed");
        setFeedback("Reference check authorization revoked. Score updated.");
        if (onSuccess)
          onSuccess(
            res.score,
            "Reference check authorization revoked (-2 points)"
          );
      }
    } catch (err: any) {
      setStatus("error");
      setErrorMessage(err.message || "Failed to execute confirmation.");
    }
  }

  function handleCancel() {
    setStatus("cancelled");
    setFeedback("Action cancelled. No changes were made.");
  }

  return (
    <div className="mt-3 rounded-xl border border-indigo-200/90 bg-white p-4 shadow-sm text-slate-800">
      <div className="flex items-start gap-3">
        <div
          className={`h-9 w-9 shrink-0 rounded-xl flex items-center justify-center ${
            isRevoke
              ? "bg-rose-50 text-rose-600"
              : isAuth
                ? "bg-amber-50 text-amber-600"
                : "bg-indigo-50 text-indigo-600"
          }`}
        >
          {isRevoke ? (
            <RotateCcw className="h-5 w-5" />
          ) : isAuth ? (
            <Award className="h-5 w-5" />
          ) : (
            <ShieldCheck className="h-5 w-5" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-xs font-bold text-slate-900">{card.title}</h4>
            <span
              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                status === "confirmed"
                  ? "bg-emerald-100 text-emerald-800"
                  : status === "cancelled"
                    ? "bg-slate-100 text-slate-600"
                    : status === "error"
                      ? "bg-rose-100 text-rose-800"
                      : "bg-indigo-50 text-indigo-700 border border-indigo-200"
              }`}
            >
              {status === "confirmed"
                ? "Confirmed"
                : status === "cancelled"
                  ? "Cancelled"
                  : status === "error"
                    ? "Action Needed"
                    : "Awaiting Action"}
            </span>
          </div>

          <p className="mt-1 text-xs text-slate-600 leading-relaxed">
            {card.description}
          </p>

          {isVerify && status === "idle" && (
            <p className="mt-1.5 text-[11px] text-amber-700 bg-amber-50 rounded-lg p-2 border border-amber-200">
              Demo only: please upload sample documents, not your real Aadhaar
              or PAN.
            </p>
          )}

          {isAuth && status === "idle" && (
            <p className="mt-1.5 text-[11px] text-slate-500">
              Authorizing lets verified recruiters and placement officers
              contact your internship company to confirm it.
            </p>
          )}

          {feedback && (
            <div
              className={`mt-2.5 rounded-lg p-2.5 text-xs flex items-center gap-2 ${
                status === "confirmed"
                  ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {status === "confirmed" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 text-slate-500 shrink-0" />
              )}
              <span>{feedback}</span>
            </div>
          )}

          {errorMessage && (
            <div className="mt-2.5 rounded-lg bg-rose-50 border border-rose-200 p-2.5 text-xs text-rose-800 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <span>{errorMessage}</span>
                {errorMessage.includes("upload a sample file first") &&
                  onOpenUpload && (
                    <button
                      onClick={onOpenUpload}
                      className="block mt-1 font-semibold text-indigo-600 hover:underline"
                    >
                      Open Document Upload →
                    </button>
                  )}
              </div>
            </div>
          )}

          {status === "idle" && (
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={handleConfirm}
                className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition ${
                  isRevoke
                    ? "bg-rose-600 hover:bg-rose-700"
                    : "bg-indigo-600 hover:bg-indigo-700"
                }`}
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>{card.button_text || "Confirm"}</span>
              </button>

              <button
                type="button"
                onClick={handleCancel}
                className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
              >
                <span>Cancel</span>
              </button>
            </div>
          )}

          {status === "loading" && (
            <div className="mt-3 flex items-center gap-2 text-xs text-indigo-600 font-medium">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Processing confirmation...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
