import AsyncStorage from "@react-native-async-storage/async-storage";

export const MOBILE_FREE_TIER_LIMITS = {
  chat_messages: 5,
  candidate_unlocks: 3,
  resume_evaluations: 1,
} as const;

export type MobileQuotaAction = keyof typeof MOBILE_FREE_TIER_LIMITS;

export type MobileSubscriptionTier =
  "free" | "student_pro" | "recruiter_pro" | "officer_pro" | "company_pro";

export type MobilePersonaRole =
  "student" | "recruiter" | "placement_officer" | "company";

const STORAGE_KEYS = {
  TIER: "nextstop_subscription_tier",
  USAGE_PREFIX: "nextstop_usage_",
};

/**
 * Check if the active mobile user currently has Pro status.
 */
export async function isMobileProUser(
  targetRole?: MobilePersonaRole
): Promise<boolean> {
  try {
    const tier = await AsyncStorage.getItem(STORAGE_KEYS.TIER);
    if (!tier || tier === "free") return false;
    if (!targetRole) return true;

    if (targetRole === "company") return tier === "company_pro";
    if (targetRole === "placement_officer") return tier === "officer_pro";
    if (targetRole === "recruiter")
      return tier === "recruiter_pro" || tier === "company_pro";
    if (targetRole === "student") return tier === "student_pro";
    return true;
  } catch {
    return false;
  }
}

/**
 * Get current mobile plan
 */
export async function getMobileCurrentPlan(): Promise<MobileSubscriptionTier> {
  try {
    const tier = await AsyncStorage.getItem(STORAGE_KEYS.TIER);
    return (tier as MobileSubscriptionTier) || "free";
  } catch {
    return "free";
  }
}

/**
 * Set Pro status locally on mobile
 */
export async function setMobileProSubscription(
  tier: MobileSubscriptionTier
): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEYS.TIER, tier);
  } catch (err) {
    console.warn("Failed to save mobile pro subscription", err);
  }
}

/**
 * Get usage count for an action
 */
export async function getMobileActionUsage(
  action: MobileQuotaAction
): Promise<number> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEYS.USAGE_PREFIX + action);
    return raw ? parseInt(raw, 10) || 0 : 0;
  } catch {
    return 0;
  }
}

/**
 * Get remaining quota for free tier
 */
export async function getMobileRemainingQuota(
  action: MobileQuotaAction,
  role?: MobilePersonaRole
): Promise<number> {
  const isPro = await isMobileProUser(role);
  if (isPro) return 999999;
  const limit = MOBILE_FREE_TIER_LIMITS[action] ?? 5;
  const used = await getMobileActionUsage(action);
  return Math.max(0, limit - used);
}

/**
 * Test whether the user can perform an action, or has exhausted their quota
 */
export async function canMobilePerformAction(
  action: MobileQuotaAction,
  role?: MobilePersonaRole
): Promise<boolean> {
  const isPro = await isMobileProUser(role);
  if (isPro) return true;
  const remaining = await getMobileRemainingQuota(action, role);
  return remaining > 0;
}

/**
 * Record usage
 */
export async function recordMobileActionUsage(
  action: MobileQuotaAction
): Promise<number> {
  try {
    const current = await getMobileActionUsage(action);
    const updated = current + 1;
    await AsyncStorage.setItem(
      STORAGE_KEYS.USAGE_PREFIX + action,
      updated.toString()
    );
    return updated;
  } catch {
    return 0;
  }
}
