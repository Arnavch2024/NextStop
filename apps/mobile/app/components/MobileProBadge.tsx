import React, { useEffect, useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Feather } from "@expo/vector-icons";
import {
  isMobileProUser,
  getMobileCurrentPlan,
  getMobileRemainingQuota,
  MobilePersonaRole,
  MobileQuotaAction,
  MobileSubscriptionTier,
} from "../../lib/subscription";

interface MobileProBadgeProps {
  role?: MobilePersonaRole;
  showQuotaFor?: MobileQuotaAction;
  onPressUpgrade?: () => void;
}

export function MobileProBadge({
  role = "student",
  showQuotaFor,
  onPressUpgrade,
}: MobileProBadgeProps) {
  const [isPro, setIsPro] = useState(false);
  const [plan, setPlan] = useState<MobileSubscriptionTier>("free");
  const [remaining, setRemaining] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function check() {
      const pro = await isMobileProUser(role);
      const currentPlan = await getMobileCurrentPlan();
      let rem: number | null = null;
      if (showQuotaFor) {
        rem = await getMobileRemainingQuota(showQuotaFor, role);
      }
      if (isMounted) {
        setIsPro(pro);
        setPlan(currentPlan);
        setRemaining(rem);
      }
    }
    check();
    return () => {
      isMounted = false;
    };
  }, [role, showQuotaFor]);

  if (isPro) {
    let bgColor = "#f59e0b"; // gold for student
    let iconName: any = "star";
    let label = "PRO";

    if (role === "company" || plan === "company_pro") {
      bgColor = "#7c3aed";
      iconName = "briefcase";
      label = "ENTERPRISE";
    } else if (role === "placement_officer" || plan === "officer_pro") {
      bgColor = "#059669";
      iconName = "shield";
      label = "OFFICER PRO";
    } else if (role === "recruiter" || plan === "recruiter_pro") {
      bgColor = "#4f46e5";
      iconName = "award";
      label = "PRO";
    }

    return (
      <TouchableOpacity
        activeOpacity={0.8}
        onPress={onPressUpgrade}
        style={[styles.proBadge, { backgroundColor: bgColor }]}
      >
        <Feather
          name={iconName}
          size={11}
          color="#ffffff"
          style={{ marginRight: 3 }}
        />
        <Text style={styles.proBadgeText}>{label}</Text>
        <View style={styles.proDot} />
      </TouchableOpacity>
    );
  }

  if (showQuotaFor && remaining !== null) {
    const isExhausted = remaining <= 0;
    return (
      <TouchableOpacity
        activeOpacity={0.7}
        onPress={onPressUpgrade}
        style={[styles.quotaBadge, isExhausted && styles.quotaBadgeExhausted]}
      >
        <Feather
          name="zap"
          size={10}
          color={isExhausted ? "#ef4444" : "#f59e0b"}
          style={{ marginRight: 3 }}
        />
        <Text
          style={[
            styles.quotaBadgeText,
            isExhausted && styles.quotaBadgeTextExhausted,
          ]}
        >
          {isExhausted ? "Limit reached" : `${remaining} left`}
        </Text>
        <Text style={styles.upgradeText}>• Upgrade</Text>
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPressUpgrade}
      style={styles.freePill}
    >
      <Text style={styles.freePillText}>Free</Text>
      <Text style={styles.freeUpgradePillText}>• $3 Pro</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  proBadge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    marginLeft: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.15,
    shadowRadius: 2,
    elevation: 2,
  },
  proBadgeText: {
    color: "#ffffff",
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 0.5,
  },
  proDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#ffffff",
    marginLeft: 4,
  },
  quotaBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1e293b",
    paddingHorizontal: 7,
    paddingVertical: 2.5,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#334155",
    marginLeft: 6,
  },
  quotaBadgeExhausted: {
    borderColor: "#ef4444",
    backgroundColor: "#450a0a",
  },
  quotaBadgeText: {
    color: "#cbd5e1",
    fontSize: 9.5,
    fontWeight: "600",
  },
  quotaBadgeTextExhausted: {
    color: "#fca5a5",
    fontWeight: "700",
  },
  upgradeText: {
    color: "#fbbf24",
    fontSize: 9.5,
    fontWeight: "700",
    marginLeft: 3,
  },
  freePill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#f1f5f9",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    marginLeft: 6,
  },
  freePillText: {
    color: "#64748b",
    fontSize: 9.5,
    fontWeight: "600",
  },
  freeUpgradePillText: {
    color: "#d97706",
    fontSize: 9.5,
    fontWeight: "700",
    marginLeft: 2,
  },
});
