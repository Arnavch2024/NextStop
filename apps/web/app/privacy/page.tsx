import fs from "fs";
import path from "path";
import Link from "next/link";
import { ArrowLeft, Shield } from "lucide-react";

function getPrivacyMarkdown(): string {
  const candidatePaths = [
    path.resolve(process.cwd(), "docs", "privacy.md"),
    path.resolve(process.cwd(), "..", "..", "docs", "privacy.md"),
    path.resolve(process.cwd(), "..", "docs", "privacy.md"),
    path.resolve(__dirname, "..", "..", "..", "..", "docs", "privacy.md"),
  ];

  for (const p of candidatePaths) {
    if (fs.existsSync(p)) {
      return fs.readFileSync(p, "utf-8");
    }
  }

  return "# Privacy approach\n\nPrivacy document could not be located on disk.";
}

export default function PrivacyPage() {
  const content = getPrivacyMarkdown();
  const lines = content.split("\n");

  return (
    <div className="min-h-screen bg-slate-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-8 sm:p-12 shadow-sm">
        <div className="mb-8 flex items-center justify-between border-b border-slate-100 pb-6">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-indigo-600 transition"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Login</span>
          </Link>
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            <Shield className="h-4 w-4 text-indigo-600" />
            <span>Privacy Documentation</span>
          </div>
        </div>

        <div className="prose prose-slate max-w-none space-y-4">
          {lines.map((rawLine, idx) => {
            const line = rawLine.trimEnd();

            if (line.startsWith("# ")) {
              return (
                <h1
                  key={idx}
                  className="text-3xl font-extrabold tracking-tight text-slate-900 mt-6 mb-4"
                >
                  {line.slice(2)}
                </h1>
              );
            }
            if (line.startsWith("## ")) {
              return (
                <h2
                  key={idx}
                  className="text-2xl font-bold tracking-tight text-slate-800 mt-8 mb-3 border-b border-slate-100 pb-2"
                >
                  {line.slice(3)}
                </h2>
              );
            }
            if (line.startsWith("### ")) {
              return (
                <h3
                  key={idx}
                  className="text-lg font-semibold text-slate-800 mt-6 mb-2"
                >
                  {line.slice(4)}
                </h3>
              );
            }
            if (line.startsWith("> ")) {
              return (
                <blockquote
                  key={idx}
                  className="rounded-xl border-l-4 border-indigo-500 bg-indigo-50/50 p-4 text-sm text-slate-700 italic my-4"
                >
                  {line.slice(2)}
                </blockquote>
              );
            }
            if (line.startsWith("- ")) {
              return (
                <li
                  key={idx}
                  className="ml-6 list-disc text-sm text-slate-600 leading-relaxed"
                >
                  {line.slice(2)}
                </li>
              );
            }
            if (/^\d+\.\s/.test(line)) {
              return (
                <li
                  key={idx}
                  className="ml-6 list-decimal text-sm text-slate-600 leading-relaxed"
                >
                  {line.replace(/^\d+\.\s*/, "")}
                </li>
              );
            }
            if (!line) {
              return <div key={idx} className="h-2" />;
            }

            return (
              <p key={idx} className="text-sm text-slate-600 leading-relaxed">
                {line}
              </p>
            );
          })}
        </div>
      </div>
    </div>
  );
}
