"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  Crown,
  Zap,
  ShieldCheck,
  Building2,
  GraduationCap,
} from "lucide-react";
import {
  isProUser,
  getCurrentPlan,
  subscribeToSubscriptionChanges,
  getRemainingQuota,
  QuotaAction,
  PersonaRole,
} from "@/lib/subscription";

interface ProBadgeProps {
  role?: PersonaRole;
  showQuotaFor?: QuotaAction;
  quotaLabel?: string;
  className?: string;
  onClickUpgrade?: () => void;
}

export function ProBadge({
  role = "student",
  showQuotaFor,
  quotaLabel,
  className = "",
  onClickUpgrade,
}: ProBadgeProps) {
  const [mounted, setMounted] = useState(false);
  const [pro, setPro] = useState(false);
  const [plan, setPlan] = useState("free");
  const [remaining, setRemaining] = useState<number | null>(null);

  const updateState = React.useCallback(() => {
    const isPro = isProUser(role);
    setPro(isPro);
    setPlan(getCurrentPlan());
    if (showQuotaFor) {
      setRemaining(getRemainingQuota(showQuotaFor));
    }
  }, [role, showQuotaFor]);

  useEffect(() => {
    setMounted(true);
    updateState();
    const unsub = subscribeToSubscriptionChanges(updateState);
    return () => unsub();
  }, [updateState]);

  if (!mounted) {
    return null;
  }

  // If user has paid / is Pro
  if (pro) {
    let badgeGradient =
      "bg-gradient-to-r from-amber-500 via-amber-600 to-yellow-500 shadow-amber-500/30 ring-1 ring-amber-300/40";
    let badgeLabel = "PRO";
    let icon = (
      <Sparkles className="h-3.5 w-3.5 fill-yellow-200 text-yellow-200 animate-pulse" />
    );
    let title = "Student Pro Member";

    if (role === "company" || plan === "company_pro") {
      badgeGradient =
        "bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-800 shadow-purple-500/30 ring-1 ring-purple-300/40";
      badgeLabel = "ENTERPRISE";
      icon = (
        <Building2 className="h-3.5 w-3.5 text-purple-200 drop-shadow-xs" />
      );
      title = "Company Enterprise Pro";
    } else if (role === "placement_officer" || plan === "officer_pro") {
      badgeGradient =
        "bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-700 shadow-emerald-500/30 ring-1 ring-emerald-300/40";
      badgeLabel = "OFFICER PRO";
      icon = (
        <GraduationCap className="h-3.5 w-3.5 text-emerald-200 drop-shadow-xs" />
      );
      title = "Placement Officer Pro";
    } else if (role === "recruiter" || plan === "recruiter_pro") {
      badgeGradient =
        "bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 shadow-indigo-500/25 ring-1 ring-indigo-400/30";
      badgeLabel = "PRO";
      icon = <Crown className="h-3.5 w-3.5 text-yellow-300 drop-shadow-xs" />;
      title = "Recruiter Pro Member";
    }

    return (
      <Link
        href="/pricing"
        title={title}
        className={`group relative inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold tracking-wide text-white shadow-xs transition-all duration-300 hover:scale-105 hover:shadow-md ${badgeGradient} ${className}`}
      >
        {/* Shimmer pulse effect */}
        <span className="absolute inset-0 rounded-full bg-white/20 opacity-0 transition-opacity group-hover:opacity-100" />
        {icon}
        <span className="text-[10px] font-black uppercase tracking-wider text-white drop-shadow-xs">
          {badgeLabel}
        </span>
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-xs ring-1 ring-white/50" />
      </Link>
    );
  }

  // If user is on Free Tier and requested quota indicator
  if (showQuotaFor && remaining !== null) {
    const isLow = remaining <= 1;
    return (
      <button
        type="button"
        onClick={onClickUpgrade}
        title="Click to upgrade for unlimited access"
        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-all hover:border-amber-400 hover:bg-amber-500/10 ${
          isLow
            ? "border-rose-400/50 bg-rose-500/10 text-rose-300 animate-pulse"
            : "border-slate-700 bg-slate-800/80 text-slate-300"
        } ${className}`}
      >
        <Zap
          className={`h-3 w-3 ${isLow ? "text-rose-400" : "text-amber-400"}`}
        />
        <span className="text-[11px]">
          {remaining > 0 ? (
            <>
              {remaining} {quotaLabel || "left"}
            </>
          ) : (
            <span className="font-semibold text-rose-300">Limit reached</span>
          )}
        </span>
        <span className="rounded bg-amber-500/20 px-1 py-0.2 text-[9px] font-semibold text-amber-300 uppercase">
          Upgrade
        </span>
      </button>
    );
  }

  // Standard subtle Free pill
  return (
    <button
      type="button"
      onClick={onClickUpgrade}
      className={`inline-flex items-center gap-1 rounded-full border border-slate-700/80 bg-slate-800/60 px-2 py-0.5 text-[10px] font-medium text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 ${className}`}
    >
      <span>Free</span>
      <span className="text-[9px] text-amber-400 font-semibold">
        • Upgrade $3
      </span>
    </button>
  );
}
