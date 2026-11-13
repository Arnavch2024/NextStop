"use client";

// Quota configuration for free tier users
export const FREE_TIER_LIMITS = {
  chat_messages: 5, // 5 AI chats for free students
  candidate_unlocks: 3, // 3 full contact unlocks for free recruiters
  resume_evaluations: 1, // 1 resume parsing & audit for free students
} as const;

export type QuotaAction = keyof typeof FREE_TIER_LIMITS;

const STORAGE_KEYS = {
  TIER: "nextstop_subscription_tier",
  PLAN: "nextstop_subscription_plan",
  EMAIL: "nextstop_subscription_email",
  EXPIRY: "nextstop_subscription_expiry",
  USAGE_PREFIX: "nextstop_usage_",
};

const CHANGE_EVENT = "nextstop_subscription_change";

export type SubscriptionTier =
  "free" | "student_pro" | "recruiter_pro" | "officer_pro" | "company_pro";

export type PersonaRole =
  "student" | "recruiter" | "placement_officer" | "company";

/**
 * Check if the active user currently has Pro status.
 */
export function isProUser(targetRole?: PersonaRole): boolean {
  if (typeof window === "undefined") return false;
  try {
    const tier = localStorage.getItem(STORAGE_KEYS.TIER);
    if (!tier || tier === "free") return false;

    if (!targetRole) return true;

    if (targetRole === "company") {
      return tier === "company_pro";
    }
    if (targetRole === "placement_officer") {
      return tier === "officer_pro";
    }
    if (targetRole === "recruiter") {
      return tier === "recruiter_pro" || tier === "company_pro";
    }
    if (targetRole === "student") {
      return tier === "student_pro";
    }
    return true;
  } catch (err) {
    console.warn("Unable to check pro status", err);
    return false;
  }
}

/**
 * Get current plan details
 */
export function getCurrentPlan(): SubscriptionTier {
  if (typeof window === "undefined") return "free";
  try {
    return (
      (localStorage.getItem(STORAGE_KEYS.TIER) as SubscriptionTier) || "free"
    );
  } catch (err) {
    console.warn("Unable to get current plan", err);
    return "free";
  }
}

/**
 * Set Pro status (called after successful checkout or webhook verification)
 */
export function setProSubscription(
  planId: "student_pro" | "recruiter_pro" | "officer_pro" | "company_pro",
  email?: string
): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEYS.TIER, planId);
    if (email) {
      localStorage.setItem(STORAGE_KEYS.EMAIL, email);
    }
    // Set 1 year expiry from now as default active buffer
    const expiry = new Date();
    expiry.setFullYear(expiry.getFullYear() + 1);
    localStorage.setItem(STORAGE_KEYS.EXPIRY, expiry.toISOString());

    window.dispatchEvent(
      new CustomEvent(CHANGE_EVENT, { detail: { plan: planId, email } })
    );
  } catch (err) {
    console.error("Failed to store pro subscription", err);
  }
}

/**
 * Sync subscription tier from Supabase profile into localStorage
 */
export function syncSubscriptionFromProfile(tier?: string | null): void {
  if (typeof window === "undefined") return;
  if (
    tier &&
    ["student_pro", "recruiter_pro", "officer_pro", "company_pro"].includes(
      tier
    )
  ) {
    setProSubscription(tier as any);
  } else if (tier === "free") {
    clearProSubscription();
  }
}

/**
 * Clear Pro subscription (e.g. on downgrade or logout)
 */
export function clearProSubscription(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEYS.TIER);
    localStorage.removeItem(STORAGE_KEYS.PLAN);
    localStorage.removeItem(STORAGE_KEYS.EMAIL);
    localStorage.removeItem(STORAGE_KEYS.EXPIRY);
    window.dispatchEvent(
      new CustomEvent(CHANGE_EVENT, { detail: { plan: "free" } })
    );
  } catch (err) {
    console.warn("Unable to clear subscription", err);
  }
}

/**
 * Get current usage count for an action
 */
export function getActionUsage(action: QuotaAction): number {
  if (typeof window === "undefined") return 0;
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.USAGE_PREFIX + action);
    return raw ? parseInt(raw, 10) || 0 : 0;
  } catch {
    return 0;
  }
}

/**
 * Get remaining quota for free tier
 */
export function getRemainingQuota(action: QuotaAction): number {
  if (isProUser()) return 999999;
  const limit = FREE_TIER_LIMITS[action] ?? 5;
  const used = getActionUsage(action);
  return Math.max(0, limit - used);
}

/**
 * Test whether the user can perform an action, or has exhausted their quota
 */
export function canPerformAction(action: QuotaAction): boolean {
  if (isProUser()) return true;
  return getRemainingQuota(action) > 0;
}

/**
 * Increment the usage counter for an action by 1
 */
export function recordActionUsage(action: QuotaAction): number {
  if (typeof window === "undefined") return 0;
  try {
    const current = getActionUsage(action);
    const updated = current + 1;
    localStorage.setItem(
      STORAGE_KEYS.USAGE_PREFIX + action,
      updated.toString()
    );
    window.dispatchEvent(
      new CustomEvent(CHANGE_EVENT, { detail: { action, usage: updated } })
    );
    return updated;
  } catch {
    return 0;
  }
}

/**
 * Reset quota for testing or admin demo
 */
export function resetQuota(action?: QuotaAction): void {
  if (typeof window === "undefined") return;
  try {
    if (action) {
      localStorage.removeItem(STORAGE_KEYS.USAGE_PREFIX + action);
    } else {
      Object.keys(FREE_TIER_LIMITS).forEach((k) => {
        localStorage.removeItem(STORAGE_KEYS.USAGE_PREFIX + k);
      });
    }
    window.dispatchEvent(
      new CustomEvent(CHANGE_EVENT, { detail: { reset: true } })
    );
  } catch (err) {
    console.warn("Unable to reset quota", err);
  }
}

/**
 * Hook or listener helper to keep components reactive to subscription changes
 */
export function subscribeToSubscriptionChanges(
  callback: () => void
): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => callback();
  window.addEventListener(CHANGE_EVENT, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(CHANGE_EVENT, handler);
    window.removeEventListener("storage", handler);
  };
}
