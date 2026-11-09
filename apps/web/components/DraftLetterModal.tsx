"use client";

import React, { useState } from "react";
import {
  X,
  Mail,
  Copy,
  Check,
  Send,
  ShieldAlert,
  Loader2,
  FileText,
} from "lucide-react";
import { LetterDraftResponse } from "@recruiting/shared";

interface DraftLetterModalProps {
  isOpen: boolean;
  onClose: () => void;
  recipientName: string;
  recipientRole?: string;
  recipientEmail?: string | null;
  defaultKind?: "invitation" | "interview" | "offer";
  onGenerateDraft: (
    kind: "invitation" | "interview" | "offer"
  ) => Promise<LetterDraftResponse>;
}

export function DraftLetterModal({
  isOpen,
  onClose,
  recipientName,
  recipientRole,
  recipientEmail,
  defaultKind = "invitation",
  onGenerateDraft,
}: DraftLetterModalProps) {
  const [kind, setKind] = useState<"invitation" | "interview" | "offer">(
    defaultKind
  );
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<LetterDraftResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  async function handleGenerate(
    selectedKind: "invitation" | "interview" | "offer"
  ) {
    setKind(selectedKind);
    setLoading(true);
    setError(null);
    try {
      const res = await onGenerateDraft(selectedKind);
      setDraft(res);
    } catch (err: any) {
      setError(err?.message || "Failed to generate letter draft.");
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!draft) return;
    const fullText = draft.subject
      ? `Subject: ${draft.subject}\n\n${draft.body}`
      : draft.body;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  const mailtoUrl = draft
    ? `mailto:${recipientEmail || ""}?subject=${encodeURIComponent(
        draft.subject || "Campus Recruiting"
      )}&body=${encodeURIComponent(draft.body)}`
    : "#";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl border border-slate-200 animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <Mail className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base">
                Draft Outreach Letter
              </h3>
              <p className="text-xs text-slate-500">
                To {recipientName} {recipientRole ? `• ${recipientRole}` : ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Strict security banner: Nothing is sent for you */}
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 flex items-start gap-2.5">
          <ShieldAlert className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-amber-900 leading-relaxed">
            <span className="font-bold">Nothing is sent for you. </span>
            The platform only creates editable drafts. You review, edit, and
            send directly from your own mail client.
          </div>
        </div>

        {/* Letter Kind Selector */}
        <div className="mt-4 flex gap-2">
          {(["invitation", "interview", "offer"] as const).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => handleGenerate(k)}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold capitalize transition ${
                kind === k
                  ? "bg-indigo-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {k} Letter
            </button>
          ))}
        </div>

        {/* Draft Content or Generate button */}
        <div className="mt-4 space-y-3">
          {loading ? (
            <div className="flex h-48 flex-col items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50">
              <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
              <p className="text-xs text-slate-500 font-medium">
                Drafting personalized letter...
              </p>
            </div>
          ) : draft ? (
            <div className="space-y-2">
              {draft.subject && (
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Subject Line
                  </label>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-xs font-semibold text-slate-800">
                    {draft.subject}
                  </div>
                </div>
              )}

              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Letter Body
                </label>
                <div className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs leading-relaxed text-slate-800 font-sans">
                  {draft.body}
                </div>
              </div>
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-600">
              {error}
            </div>
          ) : (
            <div className="flex h-36 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 p-4 text-center">
              <FileText className="h-6 w-6 text-slate-400 mb-1.5" />
              <p className="text-xs text-slate-600 font-medium">
                Click any letter type above to draft a tailored letter
              </p>
            </div>
          )}
        </div>

        {/* Action Buttons: Copy & mailto only */}
        <div className="mt-6 flex items-center justify-between pt-3 border-t border-slate-100">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
          >
            Close
          </button>

          {draft && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 hover:bg-slate-50 transition"
              >
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    <span>Copy Text</span>
                  </>
                )}
              </button>

              <a
                href={mailtoUrl}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-700 transition"
              >
                <Send className="h-3.5 w-3.5" />
                <span>Open in Mail Client</span>
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
