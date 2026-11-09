"use client";

import React, { useState, useRef } from "react";
import {
  X,
  Upload,
  FileText,
  AlertCircle,
  CheckCircle2,
  Download,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { ImportReport } from "@recruiting/shared";

interface ConsentModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description: string;
  privacyNotice: string;
  templateUrl?: string;
  templateFilename?: string;
  onUpload: (file: File) => Promise<ImportReport>;
  onSuccess?: () => void;
}

export function ConsentModal({
  isOpen,
  onClose,
  title,
  description,
  privacyNotice,
  templateUrl,
  templateFilename = "template.csv",
  onUpload,
  onSuccess,
}: ConsentModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  function resetState() {
    setFile(null);
    setError(null);
    setReport(null);
    setIsUploading(false);
  }

  function handleClose() {
    resetState();
    onClose();
  }

  async function handleUpload() {
    if (!file) return;
    setIsUploading(true);
    setError(null);

    try {
      const result = await onUpload(file);
      setReport(result);
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err?.message || "Failed to process and import file.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl border border-slate-200 animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
              <Upload className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base">{title}</h3>
              <p className="text-xs text-slate-500">CSV file import</p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Report View after successful upload */}
        {report ? (
          <div className="mt-4 space-y-4">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 flex-shrink-0" />
                <h4 className="text-sm font-bold text-emerald-900">
                  Import Completed Successfully
                </h4>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-center">
                <div className="rounded-lg bg-white/80 p-2.5 border border-emerald-100">
                  <div className="text-2xl font-extrabold text-emerald-700">
                    {report.imported}
                  </div>
                  <div className="text-[11px] font-medium text-emerald-800">
                    Records Imported
                  </div>
                </div>
                <div className="rounded-lg bg-white/80 p-2.5 border border-emerald-100">
                  <div className="text-2xl font-extrabold text-slate-600">
                    {report.skipped}
                  </div>
                  <div className="text-[11px] font-medium text-slate-600">
                    Records Skipped
                  </div>
                </div>
              </div>
            </div>

            {report.reasons && report.reasons.length > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5">
                <div className="flex items-center gap-2 text-xs font-semibold text-amber-900">
                  <AlertCircle className="h-4 w-4 text-amber-600" />
                  <span>Skipped Records Reasons</span>
                </div>
                <ul className="mt-2 max-h-40 overflow-y-auto space-y-1 text-xs text-amber-800 list-disc list-inside">
                  {report.reasons.map((r, idx) => (
                    <li key={idx} className="font-mono text-[11px]">
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-6 flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={resetState}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
              >
                Import Another File
              </button>
              <button
                type="button"
                onClick={handleClose}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 transition"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          /* Upload Form */
          <div className="mt-4 space-y-4">
            <p className="text-xs leading-relaxed text-slate-600">
              {description}
            </p>

            {/* Privacy consent banner */}
            <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-3 flex items-start gap-2.5">
              <ShieldCheck className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-blue-900">
                <span className="font-bold">Privacy Protection: </span>
                {privacyNotice}
              </div>
            </div>

            {templateUrl && (
              <div className="flex items-center justify-between text-xs text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                <span className="font-medium">Need sample format?</span>
                <a
                  href={templateUrl}
                  download={templateFilename}
                  className="inline-flex items-center gap-1 font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Download CSV Template</span>
                </a>
              </div>
            )}

            {/* File drop / picker area */}
            <input
              type="file"
              ref={fileInputRef}
              accept=".csv,text/csv"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setFile(e.target.files[0]);
                  setError(null);
                }
              }}
              className="hidden"
            />

            <div
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 cursor-pointer transition ${
                file
                  ? "border-indigo-400 bg-indigo-50/30"
                  : "border-slate-300 hover:border-indigo-400 hover:bg-slate-50"
              }`}
            >
              {file ? (
                <div className="flex items-center gap-2 text-indigo-900">
                  <FileText className="h-6 w-6 text-indigo-600" />
                  <div className="text-left">
                    <p className="text-xs font-semibold">{file.name}</p>
                    <p className="text-[10px] text-slate-500">
                      {(file.size / 1024).toFixed(1)} KB • Click to choose
                      different file
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <Upload className="h-8 w-8 text-slate-400 mb-2" />
                  <p className="text-xs font-semibold text-slate-700">
                    Click to select CSV file
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    CSV files up to 10MB supported
                  </p>
                </>
              )}
            </div>

            {error && (
              <div className="rounded-xl bg-red-50 p-3 text-xs text-red-600 flex items-center gap-2 border border-red-200">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={handleClose}
                disabled={isUploading}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleUpload}
                disabled={!file || isUploading}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 transition disabled:opacity-50"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Processing CSV...</span>
                  </>
                ) : (
                  <>
                    <Upload className="h-3.5 w-3.5" />
                    <span>Confirm & Import</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
