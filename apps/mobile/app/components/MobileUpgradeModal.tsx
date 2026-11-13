import React from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  Alert,
} from "react-native";
import { Feather } from "@expo/vector-icons";
import * as WebBrowser from "expo-web-browser";
import {
  MobilePersonaRole,
  MobileQuotaAction,
  MOBILE_FREE_TIER_LIMITS,
  setMobileProSubscription,
  MobileSubscriptionTier,
} from "../../lib/subscription";

interface MobileUpgradeModalProps {
  visible: boolean;
  onClose: () => void;
  role?: MobilePersonaRole;
  action?: MobileQuotaAction;
  onSuccessPro?: () => void;
}

export function MobileUpgradeModal({
  visible,
  onClose,
  role = "student",
  action = "chat_messages",
  onSuccessPro,
}: MobileUpgradeModalProps) {
  if (!visible) return null;

  let planId: MobileSubscriptionTier = "student_pro";
  let planTitle = "Student Pro";
  let monthlyPrice = 3;
  let annualPrice = 29;
  let features = [
    "Unlimited AI placement assistant queries",
    "Instant resume parsing & score enhancements",
    "Candidate spotlight for Mumbai recruiters",
    "Shiny PRO badge beside your name",
  ];

  if (role === "company") {
    planId = "company_pro";
    planTitle = "Company Enterprise Pro";
    monthlyPrice = 39;
    annualPrice = 349;
    features = [
      "Multi-seat team campus hiring pipelines",
      "Direct TPO & placement officer directory",
      "Unlimited candidate discovery & CGPA filtering",
      "Verified Corporate Diamond badge",
    ];
  } else if (role === "placement_officer") {
    planId = "officer_pro";
    planTitle = "Placement Officer Pro";
    monthlyPrice = 15;
    annualPrice = 149;
    features = [
      "1-Click student CSV batch imports",
      "Verified Mumbai corporate HR directory",
      "Automated document verification pipeline",
      "NIRF & NAAC placement audit reports",
    ];
  } else if (role === "recruiter") {
    planId = "recruiter_pro";
    planTitle = "Recruiter Pro";
    monthlyPrice = 19;
    annualPrice = 189;
    features = [
      "Verified direct phone & email unlocks",
      "AI-generated personalized student outreach",
      "Placement officer contact directory",
      "1-Click CSV candidate pipeline export",
    ];
  }

  const limitNumber = MOBILE_FREE_TIER_LIMITS[action] ?? 5;

  const handleOpenStripeWeb = async () => {
    try {
      await WebBrowser.openBrowserAsync(
        `https://nextstop-web.vercel.app/pricing?plan=${planId}&role=${role}`
      );
    } catch {
      Alert.alert(
        "Open in Browser",
        `Please visit https://nextstop-web.vercel.app/pricing?plan=${planId} to manage your subscription.`
      );
    }
  };

  const handleInstantTestUnlock = async () => {
    await setMobileProSubscription(planId);
    Alert.alert(
      "Pro Unlocked!",
      `Your account is now activated with ${planTitle} in Stripe test mode.`
    );
    if (onSuccessPro) onSuccessPro();
    onClose();
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          {/* Close button */}
          <TouchableOpacity
            style={styles.closeBtn}
            onPress={onClose}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <Feather name="x" size={18} color="#94a3b8" />
          </TouchableOpacity>

          {/* Header Icon */}
          <View style={styles.iconCircle}>
            <Feather name="zap" size={24} color="#f59e0b" />
          </View>

          <View style={styles.limitTag}>
            <Feather
              name="alert-circle"
              size={12}
              color="#fbbf24"
              style={{ marginRight: 4 }}
            />
            <Text style={styles.limitTagText}>
              Free Limit Reached ({limitNumber}/{limitNumber} used)
            </Text>
          </View>

          <Text style={styles.title}>Unlock {planTitle}</Text>
          <Text style={styles.subtitle}>
            Choose unlimited access with NextStop Pro for only ${monthlyPrice}
            /month (${annualPrice}/yr).
          </Text>

          {/* Feature List */}
          <View style={styles.featureBox}>
            {features.map((feat, idx) => (
              <View key={idx} style={styles.featureRow}>
                <Feather
                  name="check-circle"
                  size={14}
                  color="#10b981"
                  style={{ marginTop: 2 }}
                />
                <Text style={styles.featureText}>{feat}</Text>
              </View>
            ))}
          </View>

          {/* Primary CTA button */}
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={handleOpenStripeWeb}
            style={styles.upgradeBtn}
          >
            <Text style={styles.upgradeBtnText}>
              Upgrade Now &bull; ${monthlyPrice}/mo
            </Text>
            <Feather
              name="arrow-right"
              size={15}
              color="#0f172a"
              style={{ marginLeft: 6 }}
            />
          </TouchableOpacity>

          {/* Instant Sandbox Test Mode Unlock */}
          <TouchableOpacity
            activeOpacity={0.7}
            onPress={handleInstantTestUnlock}
            style={styles.testUnlockBtn}
          >
            <Feather
              name="unlock"
              size={12}
              color="#6366f1"
              style={{ marginRight: 4 }}
            />
            <Text style={styles.testUnlockText}>
              Activate Pro Free (Stripe Test Mode)
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.75)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  card: {
    width: "100%",
    maxWidth: 400,
    backgroundColor: "#0f172a",
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "#334155",
    padding: 24,
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.35,
    shadowRadius: 16,
    elevation: 8,
  },
  closeBtn: {
    position: "absolute",
    top: 16,
    right: 16,
    padding: 6,
  },
  iconCircle: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "rgba(245, 158, 11, 0.15)",
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.3)",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 12,
  },
  limitTag: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(245, 158, 11, 0.12)",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(245, 158, 11, 0.25)",
    marginBottom: 8,
  },
  limitTagText: {
    color: "#fbbf24",
    fontSize: 11,
    fontWeight: "700",
  },
  title: {
    color: "#ffffff",
    fontSize: 20,
    fontWeight: "800",
    textAlign: "center",
    marginBottom: 6,
  },
  subtitle: {
    color: "#94a3b8",
    fontSize: 12.5,
    textAlign: "center",
    lineHeight: 18,
    marginBottom: 16,
  },
  featureBox: {
    width: "100%",
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 14,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: "#334155",
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  featureText: {
    color: "#e2e8f0",
    fontSize: 12,
    lineHeight: 17,
    marginLeft: 8,
    flex: 1,
  },
  upgradeBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    backgroundColor: "#f59e0b",
    paddingVertical: 13,
    borderRadius: 14,
    shadowColor: "#f59e0b",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  upgradeBtnText: {
    color: "#0f172a",
    fontSize: 13.5,
    fontWeight: "800",
  },
  testUnlockBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 12,
    paddingVertical: 6,
  },
  testUnlockText: {
    color: "#818cf8",
    fontSize: 11.5,
    fontWeight: "600",
  },
});
