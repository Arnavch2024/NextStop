export default function Custom500() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4 text-center font-sans">
      <div className="max-w-md w-full rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-100 text-rose-700 font-bold text-base mb-4">
          500
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">
          Internal Server Error
        </h2>
        <p className="text-xs text-slate-600 mb-6 leading-relaxed">
          An unexpected error occurred while processing your request.
        </p>
        <a
          href="/login"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 transition shadow-xs"
        >
          Return to Login
        </a>
      </div>
    </div>
  );
}
