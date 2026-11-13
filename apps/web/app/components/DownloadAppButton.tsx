import React from "react";
import { Smartphone, Download } from "lucide-react";

export const APP_DOWNLOAD_URL =
  "https://github.com/Arnavch2024/NextStop/releases/download/v0.1.2-mobile-preview/recruiting-v0.1.2.apk";
export const APP_RELEASES_URL =
  "https://github.com/Arnavch2024/NextStop/releases/latest";

interface DownloadAppButtonProps {
  variant?: "header" | "card" | "badge";
  className?: string;
}

export function DownloadAppButton({
  variant = "header",
  className = "",
}: DownloadAppButtonProps) {
  if (variant === "card") {
    return (
      <div
        className={`rounded-2xl border border-slate-200/90 bg-gradient-to-r from-slate-50 via-white to-indigo-50/30 p-4 shadow-xs ${className}`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-600 shadow-2xs">
              <Smartphone className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-bold text-slate-900">
                  NextStop Mobile App
                </h3>
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                  Android APK
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                v0.1.2 • Cross-device sync with your web dashboard
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={APP_DOWNLOAD_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-2xs transition hover:bg-indigo-600 hover:shadow-sm"
              title="Download Android APK"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download APK</span>
            </a>
          </div>
        </div>
      </div>
    );
  }

  // Header compact button
  return (
    <a
      href={APP_DOWNLOAD_URL}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition hover:border-slate-300 hover:bg-slate-50 hover:text-indigo-600 ${className}`}
      title="Download NextStop Android App (APK)"
    >
      <Smartphone className="h-3.5 w-3.5 text-emerald-600" />
      <span>Get App</span>
      <span className="hidden sm:inline-block rounded bg-emerald-50 px-1 py-0.2 text-[9px] font-bold text-emerald-700 border border-emerald-200">
        APK
      </span>
    </a>
  );
}
