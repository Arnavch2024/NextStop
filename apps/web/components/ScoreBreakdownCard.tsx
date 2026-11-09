"use client";

import React from "react";
import {
  Award,
  CheckCircle2,
  Sparkles,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { BreakdownItem } from "@recruiting/shared";

interface ScoreBreakdownCardProps {
  title: string;
  score: number;
  subtitle?: string;
  secondaryScore?: {
    label: string;
    score: number;
  };
  breakdown: BreakdownItem[];
  nextActions?: string[];
  flagged?: string[];
  showNextActions?: boolean;
}

export function ScoreBreakdownCard({
  title,
  score,
  subtitle,
  secondaryScore,
  breakdown,
  nextActions = [],
  flagged = [],
  showNextActions = true,
}: ScoreBreakdownCardProps) {
  const clampedScore = Math.min(100, Math.max(0, score));

  return (
    <div className="space-y-4">
      {/* Score overview cards */}
      <div
        className={`grid grid-cols-1 ${secondaryScore ? "md:grid-cols-2" : "md:grid-cols-3"} gap-4`}
      >
        {/* Main Score */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {title}
              </span>
              <Award className="w-5 h-5 text-amber-500" />
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-5xl font-extrabold text-indigo-600">
                {score}
              </span>
              <span className="text-sm font-semibold text-slate-400">
                / 100
              </span>
            </div>
            {subtitle && (
              <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
            )}
          </div>

          <div className="mt-4 pt-4 border-t border-slate-100">
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div
                className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${clampedScore}%` }}
              />
            </div>
          </div>
        </div>

        {/* Secondary Score if available */}
        {secondaryScore && (
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  {secondaryScore.label}
                </span>
                <Award className="w-5 h-5 text-emerald-500" />
              </div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-5xl font-extrabold text-emerald-600">
                  {secondaryScore.score}
                </span>
                <span className="text-sm font-semibold text-slate-400">
                  / 100
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Placement & internship preparation readiness
              </p>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-100">
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-emerald-600 h-2 rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.min(100, Math.max(0, secondaryScore.score))}%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Next best actions highlight (only if no secondary score, or spanning 2 columns) */}
        {!secondaryScore && showNextActions && nextActions.length > 0 && (
          <div className="md:col-span-2 bg-gradient-to-br from-indigo-50 to-blue-50 border border-indigo-100 p-6 rounded-2xl shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 text-indigo-900 text-xs font-semibold uppercase tracking-wider">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>Next Best Action</span>
              </div>
              <p className="mt-2 text-base font-semibold text-slate-800">
                {nextActions[0]}
              </p>
            </div>
            {nextActions.length > 1 && (
              <p className="mt-2 text-xs text-slate-600">
                +{nextActions.length - 1} more recommendations to raise your
                score.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Flagged unknowns warning if any */}
      {flagged.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900">
              Flagged Incomplete Records ({flagged.length})
            </h4>
            <p className="text-xs text-amber-800 mt-1">
              Some student or college records have missing fields or unverified
              statuses:
            </p>
            <ul className="mt-2 space-y-1 list-disc list-inside text-xs text-amber-900 font-medium">
              {flagged.slice(0, 5).map((f, i) => (
                <li key={i}>{f}</li>
              ))}
              {flagged.length > 5 && (
                <li className="list-none text-[11px] text-amber-700">
                  ...and {flagged.length - 5} more
                </li>
              )}
            </ul>
          </div>
        </div>
      )}

      {/* Why is our score X? (Breakdown) */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-900">
            Why is our score {score}?
          </h2>
        </div>

        {breakdown.length === 0 ? (
          <p className="text-xs text-slate-500 py-3">
            No score points calculated yet. Import records to calculate score
            breakdown.
          </p>
        ) : (
          <div className="divide-y divide-slate-100">
            {breakdown.map((item, idx) => (
              <div
                key={idx}
                className="py-3 flex items-center justify-between text-sm"
              >
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                  <span className="font-medium text-slate-800">
                    {item.reason}
                  </span>
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-mono">
                    {item.source}
                  </span>
                </div>
                <span className="font-bold text-emerald-600">
                  +{item.points}
                </span>
              </div>
            ))}
          </div>
        )}

        {showNextActions && nextActions.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Recommendations to Improve Score
            </h3>
            <ul className="space-y-1.5 text-xs text-slate-600 list-disc list-inside">
              {nextActions.map((act, i) => (
                <li key={i}>{act}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
