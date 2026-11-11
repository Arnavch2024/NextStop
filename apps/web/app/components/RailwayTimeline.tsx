"use client";

import React from "react";
import { TimelineStation } from "@recruiting/shared";
import {
  GraduationCap,
  Briefcase,
  BookOpen,
  Building2,
  ShieldCheck,
  Award,
  CircleDot,
  Clock,
  Compass,
} from "lucide-react";

interface RailwayTimelineProps {
  stations: TimelineStation[];
  isLoading?: boolean;
}

export function RailwayTimeline({
  stations,
  isLoading = false,
}: RailwayTimelineProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-slate-400 space-y-3">
        <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-medium text-slate-500">
          Loading railway route...
        </p>
      </div>
    );
  }

  if (!stations || stations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-slate-50/60 rounded-2xl border border-dashed border-slate-200 text-center">
        <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3">
          <Compass className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-bold text-slate-800">
          Your Route Has Not Started
        </h3>
        <p className="text-xs text-slate-500 max-w-sm mt-1">
          Chat with the assistant to record your 10th, 12th, college details,
          and internships. Each milestone adds a station to your journey.
        </p>
      </div>
    );
  }

  function getStationIcon(kind: string, isCurrent: boolean, isFuture: boolean) {
    const iconClass = isCurrent
      ? "w-4 h-4 text-white"
      : isFuture
        ? "w-4 h-4 text-slate-400"
        : "w-4 h-4 text-indigo-600";

    switch (kind) {
      case "school_10":
      case "school_12":
        return <BookOpen className={iconClass} />;
      case "college":
        return <GraduationCap className={iconClass} />;
      case "internship":
        return <Briefcase className={iconClass} />;
      case "job":
        return <Building2 className={iconClass} />;
      case "pre_verify_done":
      case "pre_verify_pending":
        return <ShieldCheck className={iconClass} />;
      case "reference_done":
      case "reference_pending":
        return <Award className={iconClass} />;
      default:
        return <CircleDot className={iconClass} />;
    }
  }

  function formatYears(station: TimelineStation): string {
    if (station.is_future) {
      return "Next milestone";
    }
    if (station.start_year && station.end_year) {
      return `${station.start_year} — ${station.end_year}`;
    }
    if (station.start_year && !station.end_year) {
      return `${station.start_year} — Present`;
    }
    return station.subtitle || "";
  }

  return (
    <div className="relative pl-6 sm:pl-8">
      {/* Track Line (Vertical Railway Spine) */}
      <div className="absolute left-[23px] sm:left-[31px] top-4 bottom-4 w-1 bg-gradient-to-b from-indigo-500 via-indigo-400 to-slate-200 rounded-full" />

      <div className="space-y-6">
        {stations.map((station, idx) => {
          const isCurrent = station.is_current;
          const isFuture = station.is_future;

          return (
            <div
              key={station.id || `st-${idx}`}
              className={`relative flex items-start gap-4 transition-all ${
                isCurrent
                  ? "scale-[1.01]"
                  : isFuture
                    ? "opacity-75"
                    : "opacity-100"
              }`}
            >
              {/* Station Circle / Node */}
              <div
                className={`relative z-10 flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all shrink-0 ${
                  isCurrent
                    ? "bg-indigo-600 border-indigo-600 ring-4 ring-indigo-100 shadow-md"
                    : isFuture
                      ? "bg-slate-100 border-slate-300 border-dashed"
                      : "bg-white border-indigo-500 shadow-sm"
                }`}
              >
                {getStationIcon(station.kind, isCurrent, isFuture)}
              </div>

              {/* Station Content */}
              <div
                className={`flex-1 rounded-xl p-3 border transition-all ${
                  isCurrent
                    ? "bg-indigo-50/70 border-indigo-200 shadow-sm"
                    : isFuture
                      ? "bg-slate-50/50 border-dashed border-slate-200"
                      : "bg-white border-slate-100 shadow-sm"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-bold ${
                        isCurrent
                          ? "text-indigo-950"
                          : isFuture
                            ? "text-slate-600"
                            : "text-slate-900"
                      }`}
                    >
                      {station.title}
                    </span>

                    {/* "You are here" marker */}
                    {isCurrent && (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-indigo-600 text-white shadow-xs">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        You are here
                      </span>
                    )}

                    {station.subtitle && !isCurrent && (
                      <span className="text-xs text-slate-500 font-medium">
                        • {station.subtitle}
                      </span>
                    )}
                  </div>

                  {/* Year Tag Under/Beside Station */}
                  <div className="flex items-center gap-1 text-[11px] font-mono text-slate-500 bg-white/80 px-2 py-0.5 rounded border border-slate-200">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <span>{formatYears(station)}</span>
                  </div>
                </div>

                {station.subtitle && isCurrent && (
                  <p className="text-xs text-indigo-700 font-medium mt-1">
                    {station.subtitle}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
