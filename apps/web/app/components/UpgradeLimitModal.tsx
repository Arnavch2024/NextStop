"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  Zap,
  CheckCircle2,
  X,
  ArrowRight,
  ShieldCheck,
  Crown,
  Building2,
  GraduationCap,
  Loader2,
} from "lucide-react";
import { QuotaAction, FREE_TIER_LIMITS, PersonaRole } from "@/lib/subscription";

interface UpgradeLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
  action?: QuotaAction;
  role?: PersonaRole;
  customTitle?: string;
  customDescription?: string;
}

export function UpgradeLimitModal({
  isOpen,
  onClose,
  action = "chat_messages",
  role = "student",
  customTitle,
  customDescription,
}: UpgradeLimitModalProps) {
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">(
    "monthly"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  let planId = "student_pro";
  let monthlyPrice = 3;
  let annualPrice = 29;
  let effectiveAnnualMonthly = 2.4;
  let roleTitle = "Student Pro";
  let roleDesc =
    "Upgrade to Student Pro to continue chatting with the AI placement assistant, boost your ATS resume score, and unlock the shiny PRO badge.";
  let roleIcon = (
    <Zap className="h-7 w-7 text-slate-950 fill-slate-950 drop-shadow" />
  );
  let featureHighlight =
    "Priority placement spotlight for top Mumbai campus recruiters.";

  if (role === "company") {
    planId = "company_pro";
    monthlyPrice = 39;
    annualPrice = 349;
    effectiveAnnualMonthly = 29;
    roleTitle = "Company Enterprise Pro";
    roleDesc =
      "Upgrade to Company Pro for multi-seat campus recruitment, direct TPO hotlines, and unlimited candidate CSV pipeline exports.";
    roleIcon = <Building2 className="h-7 w-7 text-slate-950 drop-shadow" />;
    featureHighlight =
      "Multi-seat recruitment, direct TPO hotlines & unlimited candidate CSV pipeline exports.";
  } else if (role === "placement_officer") {
    planId = "officer_pro";
    monthlyPrice = 15;
    annualPrice = 149;
    effectiveAnnualMonthly = 12.4;
    roleTitle = "Placement Officer Pro";
    roleDesc =
      "Upgrade to Officer Pro to import batch student CSVs, invite top Mumbai employers, and export verified NIRF/NAAC placement audit reports.";
    roleIcon = <GraduationCap className="h-7 w-7 text-slate-950 drop-shadow" />;
    featureHighlight =
      "1-Click student CSV batch imports, recruiter invites & audit reports.";
  } else if (role === "recruiter") {
    planId = "recruiter_pro";
    monthlyPrice = 19;
    annualPrice = 189;
    effectiveAnnualMonthly = 15;
    roleTitle = "Recruiter Pro";
    roleDesc =
      "Upgrade to Recruiter Pro to unlock verified candidate contacts, direct outreach, and unlimited discovery across Mumbai universities.";
    roleIcon = <Crown className="h-7 w-7 text-slate-950 drop-shadow" />;
    featureHighlight =
      "Full verified email & phone unlocks + 1-click candidate CSV exports.";
  }

  const limitNumber = FREE_TIER_LIMITS[action] ?? 5;

  const actionNameMap: Record<QuotaAction, string> = {
    chat_messages: "AI Chat Messages",
    candidate_unlocks: "Candidate Contact Unlocks",
    resume_evaluations: "Resume Evaluations",
  };

  const handleCheckout = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/stripe/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          planId,
          billingCycle,
          role,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.checkoutUrl) {
        throw new Error(
          data.error || "Unable to start Stripe checkout session"
        );
      }

      // Redirect directly to Stripe Checkout
      window.location.href = data.checkoutUrl;
    } catch (err: any) {
      console.error("Checkout launch error:", err);
      setError(
        err?.message ||
          "Failed to initialize Stripe checkout. Please try again."
      );
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto animate-in fade-in duration-200">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-950/80 backdrop-blur-md transition-opacity"
        onClick={onClose}
      />

      {/* Modal Dialog Card */}
      <div className="relative w-full max-w-lg rounded-2xl border border-slate-700/80 bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950 p-6 sm:p-8 text-white shadow-2xl shadow-indigo-950/50 zoom-in-95 duration-200">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 rounded-full p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          aria-label="Close dialog"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Top Glow & Badge */}
        <div className="flex flex-col items-center text-center">
          <div className="relative mb-3 flex items-center justify-center">
            <div className="absolute -inset-2 rounded-full bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 opacity-60 blur-lg animate-pulse" />
            <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-slate-950 shadow-lg">
              {roleIcon}
            </div>
          </div>

          <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-300 mb-2">
            <Sparkles className="h-3 w-3 fill-amber-300" />
            <span>Free Tier Limit Reached</span>
          </div>

          <h3 className="text-xl sm:text-2xl font-black tracking-tight text-white">
            {customTitle ||
              `You've used all ${limitNumber} free ${actionNameMap[action]}`}
          </h3>

          <p className="mt-2 text-sm text-slate-300 leading-relaxed max-w-md">
            {customDescription || roleDesc}
          </p>
        </div>

        {/* Billing cycle pill selector */}
        <div className="mt-5 flex items-center justify-center">
          <div className="inline-flex rounded-xl bg-slate-800/80 p-1 border border-slate-700/60">
            <button
              type="button"
              onClick={() => setBillingCycle("monthly")}
              className={`rounded-lg px-3 py-1 text-xs font-semibold transition-all ${
                billingCycle === "monthly"
                  ? "bg-amber-500 text-slate-950 shadow-xs"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Monthly (${monthlyPrice}/mo)
            </button>
            <button
              type="button"
              onClick={() => setBillingCycle("annual")}
              className={`relative rounded-lg px-3 py-1 text-xs font-semibold transition-all ${
                billingCycle === "annual"
                  ? "bg-amber-500 text-slate-950 shadow-xs"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Annual (${annualPrice}/yr)
              <span className="ml-1 rounded-full bg-emerald-500/20 px-1.5 py-0.2 text-[9px] font-bold text-emerald-300">
                Save ~20%
              </span>
            </button>
          </div>
        </div>

        {/* Value Proposition List */}
        <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/60 p-4 space-y-2.5">
          <div className="flex items-start gap-2.5 text-xs sm:text-sm text-slate-200">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" />
            <span>
              <strong>Unlimited AI messaging</strong> without daily query caps
              or throttling.
            </span>
          </div>
          <div className="flex items-start gap-2.5 text-xs sm:text-sm text-slate-200">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
            <span>
              <strong>Shiny PRO badge</strong> rendered beside your name across
              all pages.
            </span>
          </div>
          <div className="flex items-start gap-2.5 text-xs sm:text-sm text-slate-200">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-indigo-400 mt-0.5" />
            <span>{featureHighlight}</span>
          </div>
        </div>

        {/* Pricing & CTA */}
        <div className="mt-6 space-y-3">
          {error && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-300 text-center">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={handleCheckout}
            disabled={loading}
            className="group relative flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 px-4 py-3.5 text-sm font-bold text-slate-950 shadow-lg shadow-orange-500/25 transition-all hover:scale-[1.02] hover:shadow-orange-500/40 active:scale-[0.99] disabled:opacity-60"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-slate-950" />
                <span>Opening Stripe Checkout...</span>
              </>
            ) : (
              <>
                <span>
                  Upgrade Now &bull;{" "}
                  {billingCycle === "monthly"
                    ? `$${monthlyPrice} / month`
                    : `$${annualPrice} / year (~$${effectiveAnnualMonthly}/mo)`}
                </span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </>
            )}
          </button>

          <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
            <span className="inline-flex items-center gap-1">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              Stripe Test Mode active &bull; Instant unlock
            </span>
            <Link
              href="/pricing"
              onClick={onClose}
              className="text-amber-400 hover:text-amber-300 underline underline-offset-2 transition-colors font-medium"
            >
              Compare all plans &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
