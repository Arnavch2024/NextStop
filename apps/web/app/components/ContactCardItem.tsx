"use client";

import { ContactCard } from "@recruiting/shared";
import {
  Bookmark,
  CheckCircle2,
  ExternalLink,
  FileEdit,
  Loader2,
  Trash2,
} from "lucide-react";

interface ContactCardItemProps {
  contact: ContactCard;
  isSaved: boolean;
  isBusy?: boolean;
  onSave?: (contactId: string) => void;
  onRemove?: (contactId: string) => void;
  onDraft: (contact: ContactCard) => void;
  showRemoveOnly?: boolean;
}

export function ContactCardItem({
  contact,
  isSaved,
  isBusy = false,
  onSave,
  onRemove,
  onDraft,
  showRemoveOnly = false,
}: ContactCardItemProps) {
  const isUnverified = contact.unverified !== false;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3.5 text-slate-800 shadow-2xs transition hover:border-slate-300">
      {/* Top row: Name, title, and verification badge */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-slate-900 text-sm">
            {contact.name}
          </div>
          <div className="text-xs text-slate-600 mt-0.5">
            {contact.title || "Recruiter"}
            {contact.company_name ? ` at ${contact.company_name}` : ""}
            {contact.college_name ? ` (${contact.college_name})` : ""}
          </div>
          {contact.location && (
            <div className="text-[11px] text-slate-500 mt-0.5">
              📍 {contact.location}
            </div>
          )}
        </div>
        <div>
          <span
            className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-medium border ${
              isUnverified
                ? "bg-amber-50 text-amber-800 border-amber-200"
                : "bg-emerald-50 text-emerald-800 border-emerald-200"
            }`}
          >
            {isUnverified ? "Unverified, check the source" : "Verified"}
          </span>
        </div>
      </div>

      {/* Source badges row */}
      {contact.sources && contact.sources.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {contact.sources.map((src, i) => {
            const label =
              src.source === "seed"
                ? "Seed"
                : src.source === "resume"
                  ? "Resume"
                  : src.source === "user_said"
                    ? "User said"
                    : "Web";
            const domain = src.domain;
            const fetchedDate = src.fetched_at?.slice(0, 10);

            return (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-700"
              >
                <span>{label}</span>
                {domain && (
                  <span className="text-slate-400 font-mono text-[9px]">
                    ({domain})
                  </span>
                )}
                {fetchedDate && (
                  <span className="text-slate-400 text-[9px]">
                    • {fetchedDate}
                  </span>
                )}
              </span>
            );
          })}
        </div>
      )}

      {/* Bottom metadata and action buttons */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2.5 text-xs">
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
          {contact.source_url && (
            <a
              href={contact.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 underline font-medium"
            >
              Source <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {contact.source_published_date && (
            <span>As of: {contact.source_published_date.slice(0, 10)}</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Draft message action button */}
          <button
            type="button"
            onClick={() => onDraft(contact)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition shadow-2xs cursor-pointer"
          >
            <FileEdit className="h-3.5 w-3.5" />
            <span>Draft message</span>
          </button>

          {/* Save / Remove Actions */}
          {showRemoveOnly ? (
            <button
              type="button"
              onClick={() => onRemove && onRemove(contact.id)}
              disabled={isBusy}
              className="inline-flex items-center gap-1 rounded-lg border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-100 transition disabled:opacity-50 cursor-pointer"
            >
              {isBusy ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              <span>Remove</span>
            </button>
          ) : isSaved ? (
            <div className="flex items-center gap-1.5">
              <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Saved</span>
              </span>
              <button
                type="button"
                onClick={() => onRemove && onRemove(contact.id)}
                disabled={isBusy}
                title="Remove from saved list"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-500 hover:border-red-200 hover:bg-red-50 hover:text-red-700 transition disabled:opacity-50"
              >
                {isBusy ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Trash2 className="h-3 w-3" />
                )}
                <span>Remove</span>
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => onSave && onSave(contact.id)}
              disabled={isBusy}
              className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 shadow-2xs transition disabled:opacity-50 cursor-pointer"
            >
              {isBusy ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Bookmark className="h-3.5 w-3.5" />
                  <span>Save to my list</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
