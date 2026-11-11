import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 text-center">
      <div className="max-w-md w-full rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-700 font-bold text-base mb-4">
          404
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">
          Page Not Found
        </h2>
        <p className="text-xs text-slate-600 mb-6 leading-relaxed">
          The requested page does not exist or demo mode is currently disabled
          in this environment.
        </p>
        <Link
          href="/login"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 transition shadow-2xs"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Return to Login</span>
        </Link>
      </div>
    </div>
  );
}
