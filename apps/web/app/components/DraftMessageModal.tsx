"use client";

import { useState, useEffect } from "react";
import { ContactCard, draftOutreach, ApiError } from "@recruiting/shared";
import { API_BASE_URL } from "@/lib/supabase";
import {
  X,
  Mail,
  Linkedin,
  Copy,
  Check,
  Send,
  Loader2,
  AlertCircle,
  ExternalLink,
  ShieldAlert,
} from "lucide-react";

interface DraftMessageModalProps {
  isOpen: boolean;
  onClose: () => void;
  contact: ContactCard | null;
  token: string | null;
  onToast?: (message: string) => void;
}

export function DraftMessageModal({
  isOpen,
  onClose,
  contact,
  token,
  onToast,
}: DraftMessageModalProps) {
  const [channel, setChannel] = useState<"email" | "linkedin">("email");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (!isOpen || !contact || !token) {
      setSubject("");
      setBody("");
      setError(null);
      return;
    }

    let isMounted = true;

    async function fetchDraft() {
      setIsLoading(true);
      setError(null);
      setIsCopied(false);

      try {
        const response = await draftOutreach(API_BASE_URL, token!, {
          contact_id: contact!.id,
          channel,
        });

        if (isMounted) {
          setSubject(response.subject || "");
          setBody(response.body || "");
        }
      } catch (err: any) {
        if (!isMounted) return;
        if (err instanceof ApiError && err.status === 429) {
          setError(
            "Rate limit reached. Please wait a moment before trying again."
          );
        } else {
          setError(
            err.message ||
              "Failed to generate outreach draft. Please try again."
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchDraft();

    return () => {
      isMounted = false;
    };
  }, [isOpen, contact, token, channel]);

  if (!isOpen || !contact) return null;

  async function handleCopy() {
    try {
      const textToCopy =
        channel === "email" && subject
          ? `Subject: ${subject}\n\n${body}`
          : body;
      await navigator.clipboard.writeText(textToCopy);
      setIsCopied(true);
      if (onToast) {
        onToast(
          channel === "email" ? "Email draft copied!" : "LinkedIn note copied!"
        );
      }
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      if (onToast) onToast("Failed to copy to clipboard");
    }
  }

  function handleMailto() {
    const emailTo = contact?.email || "";
    const encodedSubject = encodeURIComponent(subject);
    const encodedBody = encodeURIComponent(body);
    const mailtoUrl = `mailto:${emailTo}?subject=${encodedSubject}&body=${encodedBody}`;
    window.location.href = mailtoUrl;
    if (onToast) {
      onToast("Opening your default mail client...");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs animate-in fade-in">
      <div className="relative flex max-h-[90vh] w-full max-w-lg flex-col rounded-2xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 p-5 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
                Draft Message
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-900">
              {contact.name}
            </h3>
            <p className="text-xs text-slate-500">
              {contact.title || "Recruiter"}
              {contact.company_name ? ` at ${contact.company_name}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Channel Selector Tabs */}
        <div className="border-b border-slate-100 px-5 pt-3">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setChannel("email")}
              className={`flex items-center gap-1.5 border-b-2 px-3 pb-2.5 text-xs font-semibold transition ${
                channel === "email"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <Mail className="h-3.5 w-3.5" />
              <span>Email Draft</span>
            </button>
            <button
              type="button"
              onClick={() => setChannel("linkedin")}
              className={`flex items-center gap-1.5 border-b-2 px-3 pb-2.5 text-xs font-semibold transition ${
                channel === "linkedin"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              <Linkedin className="h-3.5 w-3.5" />
              <span>LinkedIn Note</span>
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Prominent Mandatory Safety Warning */}
          <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-900">
            <ShieldAlert className="h-4 w-4 shrink-0 text-amber-600" />
            <span className="font-semibold">
              Review before sending. Nothing is sent for you.
            </span>
          </div>

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-400">
              <Loader2 className="h-7 w-7 animate-spin text-indigo-600" />
              <p className="mt-2 text-xs font-medium text-slate-600">
                Generating personalized draft...
              </p>
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700">
              <div className="flex items-center gap-2 font-semibold">
                <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />
                <span>Error generating draft</span>
              </div>
              <p className="mt-1 text-slate-600">{error}</p>
              <button
                type="button"
                onClick={() => setChannel((prev) => prev)}
                className="mt-3 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
              >
                Try Again
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {channel === "email" && (
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
                    Subject
                  </label>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 focus:border-indigo-500 focus:bg-white focus:outline-hidden"
                  />
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    {channel === "email"
                      ? "Email Body"
                      : "LinkedIn Note (under 300 chars)"}
                  </label>
                  {channel === "linkedin" && (
                    <span
                      className={`text-[10px] font-medium ${
                        body.length > 300
                          ? "text-red-500 font-bold"
                          : "text-slate-400"
                      }`}
                    >
                      {body.length}/300 chars
                    </span>
                  )}
                </div>
                <textarea
                  rows={channel === "email" ? 7 : 4}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  className="w-full resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800 leading-relaxed focus:border-indigo-500 focus:bg-white focus:outline-hidden font-sans"
                />
              </div>

              {channel === "linkedin" && contact.linkedin_url && (
                <div className="text-[11px] text-slate-500">
                  <span>Profile: </span>
                  <a
                    href={contact.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-indigo-600 hover:underline font-medium"
                  >
                    Open LinkedIn profile <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/70 p-4 rounded-b-2xl">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
          >
            Close
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopy}
              disabled={isLoading || !!error || !body}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition disabled:opacity-50"
            >
              {isCopied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                  <span className="text-emerald-700">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span>Copy</span>
                </>
              )}
            </button>

            {channel === "email" && (
              <button
                type="button"
                onClick={handleMailto}
                disabled={isLoading || !!error || !body}
                className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-indigo-700 transition disabled:opacity-50"
              >
                <Send className="h-3.5 w-3.5" />
                <span>Open in Email (mailto)</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
