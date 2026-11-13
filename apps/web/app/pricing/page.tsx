"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Check,
  Sparkles,
  Zap,
  ArrowRight,
  ShieldCheck,
  CreditCard,
  ArrowLeft,
  Loader2,
  Lock,
  Building2,
  GraduationCap,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";
import { getCurrentSession } from "@/lib/auth";
import { PRICING_PLANS } from "@/lib/stripe";

function PricingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [billingInterval, setBillingInterval] = useState<"month" | "year">(
    "month"
  );
  const [activeRoleTab, setActiveRoleTab] = useState<"student" | "recruiter">(
    "student"
  );
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [userSession, setUserSession] = useState<any>(null);
  const [currentTier, setCurrentTier] = useState<string>("free");

  const isSuccess = searchParams?.get("success") === "true";
  const isCanceled = searchParams?.get("canceled") === "true";
  const successPlan = searchParams?.get("plan");

  useEffect(() => {
    getCurrentSession().then((session) => {
      if (session) {
        setUserSession(session);
        if (
          session.user.role === "recruiter" ||
          session.user.role === "company"
        ) {
          setActiveRoleTab("recruiter");
        }
        // Fetch current subscription status
        fetch(`/api/stripe/status?userId=${session.user.id}`)
          .then((res) => res.json())
          .then((data) => {
            if (data?.tier) setCurrentTier(data.tier);
          })
          .catch(() => {});
      }
    });
  }, []);

  async function handleCheckout(planId: string) {
    if (planId === "free") {
      router.push("/chat");
      return;
    }

    setLoadingPlan(planId);
    setCheckoutError(null);

    try {
      const res = await fetch("/api/stripe/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan: planId,
          interval: billingInterval,
          userId: userSession?.user?.id || null,
          userEmail: userSession?.user?.email || null,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || "Failed to start checkout");
      }

      if (data.url) {
        window.location.href = data.url;
      } else {
        throw new Error("No checkout URL returned from server.");
      }
    } catch (err: any) {
      setCheckoutError(
        err.message || "Checkout failed to initialize. Please try again."
      );
      setLoadingPlan(null);
    }
  }

  const studentPlans = [PRICING_PLANS.free, PRICING_PLANS.student_pro];
  const recruiterPlans = [PRICING_PLANS.free, PRICING_PLANS.recruiter_pro];
  const displayedPlans =
    activeRoleTab === "student" ? studentPlans : recruiterPlans;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans pb-24">
      {/* Top Header */}
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Chat</span>
          </Link>

          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-2xs">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="text-sm font-bold text-slate-900 tracking-tight">
              NextStop Pro
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">
              <CreditCard className="h-3 w-3" />
              <span>Stripe Test Mode</span>
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-5xl mx-auto px-4 pt-10 sm:pt-14">
        {/* Success Alert Banner */}
        {isSuccess && (
          <div className="mb-8 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-5 shadow-xs animate-in fade-in slide-in-from-top-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-sm">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-bold text-emerald-900">
                  Subscription Activated!
                </h3>
                <p className="text-xs text-emerald-700 mt-0.5">
                  Your{" "}
                  {successPlan === "recruiter_pro"
                    ? "Recruiter Pro"
                    : "Student Pro"}{" "}
                  membership is now live. All advanced candidate tools, AI
                  features, and verification badges are fully unlocked.
                </p>
              </div>
              <Link
                href="/chat"
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-700 transition shadow-2xs"
              >
                <span>Open Chat</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        )}

        {/* Cancellation Notice */}
        {isCanceled && (
          <div className="mb-8 rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600 shadow-xs flex items-center justify-between">
            <span>Checkout was canceled. No charges were made.</span>
            <button
              onClick={() => router.replace("/pricing")}
              className="font-semibold text-indigo-600 hover:underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Error Alert */}
        {checkoutError && (
          <div className="mb-8 rounded-2xl border border-red-200 bg-red-50 p-4 text-xs text-red-700 shadow-xs">
            {checkoutError}
          </div>
        )}

        {/* Hero Section */}
        <div className="text-center max-w-2xl mx-auto mb-10">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50/80 px-3 py-1 text-xs font-semibold text-indigo-700 shadow-2xs mb-4">
            <Zap className="h-3.5 w-3.5 fill-indigo-600 text-indigo-600" />
            <span>Accelerate Your Recruiting Experience</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight">
            Simple, Transparent Tiers
          </h1>
          <p className="mt-3 text-sm text-slate-600 leading-relaxed">
            Choose the plan that fits your campus journey. From automated resume
            readiness scoring to enterprise recruiter discovery tools.
          </p>

          {/* Role Persona Toggle */}
          <div className="mt-8 inline-flex p-1 bg-slate-200/80 rounded-2xl border border-slate-200 shadow-inner">
            <button
              type="button"
              onClick={() => setActiveRoleTab("student")}
              className={`flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold transition ${
                activeRoleTab === "student"
                  ? "bg-white text-indigo-600 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <GraduationCap className="h-4 w-4" />
              <span>For Students & Candidates</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveRoleTab("recruiter")}
              className={`flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold transition ${
                activeRoleTab === "recruiter"
                  ? "bg-white text-indigo-600 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Building2 className="h-4 w-4" />
              <span>For Recruiters & Companies</span>
            </button>
          </div>

          {/* Billing Interval Toggle */}
          <div className="mt-5 flex items-center justify-center gap-3">
            <span
              className={`text-xs font-medium ${
                billingInterval === "month"
                  ? "text-slate-900 font-bold"
                  : "text-slate-500"
              }`}
            >
              Monthly
            </span>
            <button
              type="button"
              onClick={() =>
                setBillingInterval(
                  billingInterval === "month" ? "year" : "month"
                )
              }
              className="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent bg-slate-300 transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500"
              style={{
                backgroundColor:
                  billingInterval === "year" ? "#4f46e5" : "#cbd5e1",
              }}
              aria-label="Toggle annual billing"
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition duration-200 ease-in-out ${
                  billingInterval === "year" ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
            <span
              className={`text-xs font-medium flex items-center gap-1.5 ${
                billingInterval === "year"
                  ? "text-slate-900 font-bold"
                  : "text-slate-500"
              }`}
            >
              <span>Annual</span>
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                Save 18%
              </span>
            </span>
          </div>
        </div>

        {/* Pricing Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto items-stretch">
          {displayedPlans.map((plan) => {
            const isCurrent = currentTier === plan.id;
            const price =
              billingInterval === "year" ? plan.annualPrice : plan.monthlyPrice;
            const pricePeriod = billingInterval === "year" ? "/year" : "/month";

            return (
              <div
                key={plan.id}
                className={`relative rounded-3xl p-8 flex flex-col justify-between transition-all duration-200 ${
                  plan.highlighted
                    ? "bg-white border-2 border-indigo-600 shadow-xl shadow-indigo-100/50 scale-[1.02]"
                    : "bg-white border border-slate-200 shadow-sm hover:border-slate-300"
                }`}
              >
                {/* Highlighted Badge */}
                {plan.highlighted && plan.badge && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                    <span className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-indigo-600 to-blue-600 px-3.5 py-1 text-[11px] font-bold text-white shadow-sm uppercase tracking-wider">
                      <Sparkles className="h-3 w-3" />
                      {plan.badge}
                    </span>
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between">
                    <h3 className="text-xl font-bold text-slate-900">
                      {plan.name}
                    </h3>
                    {isCurrent && (
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-2 min-h-[36px]">
                    {plan.description}
                  </p>

                  {/* Price */}
                  <div className="mt-6 flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold text-slate-900 tracking-tight">
                      ${price}
                    </span>
                    <span className="text-xs text-slate-500 font-semibold">
                      {pricePeriod}
                    </span>
                  </div>

                  {billingInterval === "year" && plan.monthlyPrice > 0 && (
                    <p className="text-[11px] text-emerald-600 font-semibold mt-1">
                      Billed annually (${(price / 12).toFixed(1)}/mo)
                    </p>
                  )}

                  {/* Divider */}
                  <div className="my-6 border-t border-slate-100" />

                  {/* Feature Checklist */}
                  <div className="space-y-3.5 mb-8">
                    <p className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                      What&rsquo;s included:
                    </p>
                    {plan.features.map((feat, idx) => (
                      <div key={idx} className="flex items-start gap-2.5">
                        <div
                          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
                            plan.highlighted
                              ? "bg-indigo-100 text-indigo-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          <Check className="h-2.5 w-2.5 stroke-[3]" />
                        </div>
                        <span className="text-xs text-slate-600 leading-relaxed">
                          {feat}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Call to Action Button */}
                <button
                  type="button"
                  onClick={() => handleCheckout(plan.id)}
                  disabled={loadingPlan !== null || isCurrent}
                  className={`w-full py-3 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                    isCurrent
                      ? "bg-slate-100 text-slate-400 cursor-default"
                      : plan.highlighted
                        ? "bg-indigo-600 text-white hover:bg-indigo-700 focus:ring-indigo-500 shadow-md shadow-indigo-200"
                        : "bg-slate-900 text-white hover:bg-slate-800 focus:ring-slate-900 shadow-sm"
                  }`}
                >
                  {loadingPlan === plan.id ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Redirecting to Stripe...</span>
                    </>
                  ) : isCurrent ? (
                    <span>Your Current Plan</span>
                  ) : (
                    <>
                      <span>{plan.ctaLabel}</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Stripe Sandbox Test Notice Banner */}
        <div className="mt-14 rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs max-w-3xl mx-auto">
          <div className="flex items-start gap-3.5">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50 border border-amber-200 text-amber-700">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-900 flex items-center gap-2">
                <span>Stripe Test Mode Sandbox Active</span>
                <span className="rounded bg-amber-100 px-1.5 py-0.2 text-[9px] font-extrabold text-amber-800">
                  NO REAL CHARGES
                </span>
              </h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                You can safely test the complete subscription flow without
                moving real money. When redirected to the Stripe Checkout page,
                use any test card details:
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-[11px] text-slate-800 font-semibold border border-slate-200">
                  Card: 4242 4242 4242 4242
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-[11px] text-slate-800 font-semibold border border-slate-200">
                  Exp: Any future date (e.g. 12/28)
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-[11px] text-slate-800 font-semibold border border-slate-200">
                  CVC: Any 3 digits (e.g. 123)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Frequently Asked Questions */}
        <div className="mt-16 max-w-2xl mx-auto">
          <h3 className="text-center text-lg font-bold text-slate-900 mb-6 flex items-center justify-center gap-2">
            <HelpCircle className="h-5 w-5 text-indigo-600" />
            <span>Frequently Asked Questions</span>
          </h3>

          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
              <h4 className="text-xs font-bold text-slate-900">
                Can I switch between plans at any time?
              </h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Yes. You can upgrade, downgrade, or cancel your subscription at
                any time with prorated billing applied automatically.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
              <h4 className="text-xs font-bold text-slate-900">
                Do I need to connect a bank account for test payments?
              </h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                No. The platform is configured in Stripe Test Mode, so you can
                simulate realistic payment cycles without requiring any bank or
                merchant payouts.
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
              <h4 className="text-xs font-bold text-slate-900">
                How does cross-device sync work with Pro features?
              </h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Subscriptions are tied to your central Supabase profile UUID.
                Whether you use the web app or Android APK, your Pro status
                syncs live across devices in real time.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function PricingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-50">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
            <p className="text-xs font-semibold text-slate-500">
              Loading pricing options...
            </p>
          </div>
        </div>
      }
    >
      <PricingContent />
    </Suspense>
  );
}
