"use client";

import React, { useState, useRef } from "react";
import {
  uploadResume,
  verifyMock,
  revokeVerifyMock,
  DocumentRecord,
  ScoreResponse,
} from "@recruiting/shared";
import {
  ShieldCheck,
  UploadCloud,
  FileText,
  AlertTriangle,
  X,
  CheckCircle2,
  Trash2,
  Loader2,
  Info,
} from "lucide-react";

interface PreVerifySheetProps {
  isOpen: boolean;
  onClose: () => void;
  token: string;
  baseUrl: string;
  documents?: DocumentRecord[];
  onSuccess: (score?: ScoreResponse) => void;
}

export function PreVerifySheet({
  isOpen,
  onClose,
  token,
  baseUrl,
  documents = [],
  onSuccess,
}: PreVerifySheetProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<"aadhaar" | "pan" | "other">(
    "aadhaar"
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  // Active verified document if present
  const verifiedDoc = documents.find((d) => d.verified_flag);
  const uploadedDoc = documents[0];

  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    setError(null);
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];

    const validMimes = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/msword",
    ];
    const isDocx = file.name.endsWith(".docx") || file.name.endsWith(".doc");
    const isPdf = file.name.endsWith(".pdf");

    if (!validMimes.includes(file.type) && !isDocx && !isPdf) {
      setError("Please choose a PDF or Word document (.pdf, .docx).");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("File exceeds maximum allowed size of 5 MB.");
      return;
    }

    setSelectedFile(file);
  }

  async function handleUploadAndVerify() {
    if (!selectedFile) {
      setError("Please select a sample document first.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      // 1. Upload sample file safely to private storage
      const uploadRes = await uploadResume(
        baseUrl,
        selectedFile,
        selectedFile.name,
        token
      );

      // 2. Automatically trigger mock verification
      const verifyRes = await verifyMock(baseUrl, token, {
        document_id: uploadRes.document_id,
        document_type: docType,
      });

      setSuccessMessage(
        "Sample document pre-verified! +2 points added to score."
      );
      onSuccess(verifyRes.score);
      setSelectedFile(null);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      if (err.status === 404) {
        setError("Verification is not enabled in this environment.");
      } else {
        setError(err.message || "Failed to complete demo verification.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRemoveDocuments() {
    if (
      !confirm(
        "Are you sure you want to remove your documents and revoke verification?"
      )
    ) {
      return;
    }

    setIsRevoking(true);
    setError(null);

    try {
      const res = await revokeVerifyMock(baseUrl, token);
      setSuccessMessage("Documents removed and verification revoked.");
      onSuccess(res.score);
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to remove documents.");
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
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Document Pre-Verification
              </h3>
              <p className="text-xs text-slate-500">
                Mock verify credentials for +2 readiness points
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

        {/* Demo-only prominent warning banner */}
        <div className="mt-4 rounded-xl bg-amber-50 border border-amber-200 p-3.5 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs text-amber-900 leading-relaxed">
            <p className="font-bold">
              Demo only: please upload sample documents, not your real Aadhaar
              or PAN.
            </p>
            <p className="text-amber-800 mt-0.5">
              This environment runs mocked verification for MVP testing. Never
              upload authentic government-issued identity documents.
            </p>
          </div>
        </div>

        {/* Plain-language explanation: What is read vs What is stored */}
        <div className="mt-4 rounded-xl bg-slate-50 border border-slate-200/80 p-3.5 space-y-2 text-xs">
          <div className="flex items-start gap-2 text-slate-700">
            <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-slate-900">What is read: </span>
              Only document MIME type (PDF/Word) and file size to ensure valid
              upload. The application never reads file contents or ID numbers.
            </div>
          </div>
          <div className="flex items-start gap-2 text-slate-700 pl-6">
            <div>
              <span className="font-bold text-slate-900">What is stored: </span>
              Document type, verification status, timestamp, and a masked tail
              identifier (e.g. XXXX-XXXX-1234) provided by the verification
              service.
            </div>
          </div>
          <div className="flex items-start gap-2 text-slate-700 pl-6">
            <div>
              <span className="font-bold text-slate-900">
                What is NEVER stored:{" "}
              </span>
              No full Aadhaar or PAN numbers, no address details, and no
              document text is ever parsed, logged, or sent to any LLM.
            </div>
          </div>
        </div>

        {/* Current status chip and document card */}
        {(verifiedDoc || uploadedDoc) && (
          <div className="mt-4 p-3.5 rounded-xl border border-slate-200 bg-white shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Current Status
              </span>
              <div className="flex items-center gap-1.5">
                {verifiedDoc ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    Verified (mocked)
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200">
                    Uploaded
                  </span>
                )}
              </div>
            </div>

            {verifiedDoc?.masked_id_tail && (
              <div className="mt-2 text-xs text-slate-700 flex items-center justify-between bg-slate-50 p-2 rounded-lg border border-slate-100">
                <span className="text-slate-500">Masked ID Identifier:</span>
                <span className="font-mono font-bold text-slate-900">
                  {verifiedDoc.masked_id_tail}
                </span>
              </div>
            )}

            <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
              <span className="text-slate-500">
                {verifiedDoc?.file_name ||
                  uploadedDoc?.file_name ||
                  "Document on file"}
              </span>
              <button
                type="button"
                onClick={handleRemoveDocuments}
                disabled={isRevoking}
                className="inline-flex items-center gap-1 text-red-600 hover:text-red-700 font-semibold transition disabled:opacity-50"
              >
                {isRevoking ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                <span>Remove my documents</span>
              </button>
            </div>
          </div>
        )}

        {/* Upload Form */}
        <div className="mt-4 space-y-3">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Select Sample Document Type
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(["aadhaar", "pan", "other"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setDocType(t)}
                  className={`py-2 px-3 rounded-lg text-xs font-semibold border text-center capitalize transition ${
                    docType === t
                      ? "border-indigo-600 bg-indigo-50 text-indigo-700 shadow-xs"
                      : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelected}
              accept=".pdf,.docx,.doc"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-full border-2 border-dashed border-slate-200 hover:border-indigo-300 rounded-xl p-4 text-center transition bg-slate-50/50 hover:bg-indigo-50/30 group"
            >
              <UploadCloud className="w-7 h-7 mx-auto text-slate-400 group-hover:text-indigo-600 mb-1.5 transition" />
              {selectedFile ? (
                <div className="flex items-center justify-center gap-2 text-xs font-bold text-indigo-700">
                  <FileText className="w-4 h-4" />
                  <span>{selectedFile.name}</span>
                </div>
              ) : (
                <>
                  <p className="text-xs font-bold text-slate-700">
                    Choose sample document file
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    PDF or DOCX (max 5 MB)
                  </p>
                </>
              )}
            </button>
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
            disabled={!selectedFile || isSubmitting}
            onClick={handleUploadAndVerify}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition disabled:opacity-50"
          >
            {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>I Agree & Verify Mock</span>
          </button>
        </div>
      </div>
    </div>
  );
}
