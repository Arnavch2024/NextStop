import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import {
  ConfirmationCard,
  verifyMock,
  authorizeReferenceCheck,
  revokeReferenceCheck,
  ScoreResponse,
} from "@recruiting/shared";

interface MobileChatConfirmationCardProps {
  card: ConfirmationCard;
  token: string;
  baseUrl: string;
  onSuccess?: (score?: ScoreResponse, message?: string) => void;
  onOpenUpload?: () => void;
}

export function MobileChatConfirmationCard({
  card,
  token,
  baseUrl,
  onSuccess,
  onOpenUpload,
}: MobileChatConfirmationCardProps) {
  const [status, setStatus] = useState<
    "idle" | "loading" | "confirmed" | "cancelled" | "error"
  >("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const isVerify =
    card.action === "verify_mock" || card.type === "verify_mock_confirmation";
  const isAuth =
    card.action === "authorize_reference_check" ||
    card.type === "reference_check_confirmation";
  const isRevoke =
    card.action === "revoke_reference_check" ||
    card.type === "revoke_reference_check_confirmation";

  async function handleConfirm() {
    setStatus("loading");
    setErrorMessage(null);

    try {
      if (isVerify) {
        try {
          const res = await verifyMock(baseUrl, token, {
            document_type: card.document_type || "aadhaar",
          });
          setStatus("confirmed");
          setFeedback(
            `Sample document pre-verified! +2 points added. Status: ${res.verification_note || "Demo verification (mocked)"}`
          );
          if (onSuccess)
            onSuccess(res.score, "Document pre-verified (+2 points)");
        } catch (err: any) {
          if (
            err.status === 404 &&
            err.message?.includes("No document found")
          ) {
            setStatus("error");
            setErrorMessage(
              "No sample document uploaded yet. Please upload a sample file first."
            );
            if (onOpenUpload) onOpenUpload();
          } else if (err.status === 404) {
            setStatus("error");
            setErrorMessage("Verification is not enabled in this environment.");
          } else {
            setStatus("error");
            setErrorMessage(err.message || "Failed to verify document.");
          }
        }
      } else if (isAuth) {
        const res = await authorizeReferenceCheck(baseUrl, token, {
          authorized_party: card.company || "Campus Placement Cell",
          authorized_role: "Intern",
        });
        setStatus("confirmed");
        setFeedback(
          "Reference check authorized! +2 points added to readiness score."
        );
        if (onSuccess)
          onSuccess(res.score, "Reference check authorized (+2 points)");
      } else if (isRevoke) {
        const res = await revokeReferenceCheck(baseUrl, token);
        setStatus("confirmed");
        setFeedback("Reference check authorization revoked. Score updated.");
        if (onSuccess)
          onSuccess(
            res.score,
            "Reference check authorization revoked (-2 points)"
          );
      }
    } catch (err: any) {
      setStatus("error");
      setErrorMessage(err.message || "Failed to execute confirmation.");
    }
  }

  function handleCancel() {
    setStatus("cancelled");
    setFeedback("Action cancelled. No changes were made.");
  }

  const badgeColor =
    status === "confirmed"
      ? "#059669"
      : status === "cancelled"
        ? "#64748B"
        : status === "error"
          ? "#DC2626"
          : "#4F46E5";

  const badgeBg =
    status === "confirmed"
      ? "#ECFDF5"
      : status === "cancelled"
        ? "#F1F5F9"
        : status === "error"
          ? "#FEF2F2"
          : "#EEF2FF";

  return (
    <View style={styles.cardContainer}>
      <View style={styles.headerRow}>
        <View style={styles.iconCircle}>
          <Text style={styles.iconText}>
            {isRevoke ? "↩️" : isAuth ? "🎖️" : "🛡️"}
          </Text>
        </View>
        <View style={{ flex: 1 }}>
          <View style={styles.titleRow}>
            <Text style={styles.titleText}>{card.title}</Text>
            <View style={[styles.badge, { backgroundColor: badgeBg }]}>
              <Text style={[styles.badgeText, { color: badgeColor }]}>
                {status === "confirmed"
                  ? "Confirmed"
                  : status === "cancelled"
                    ? "Cancelled"
                    : status === "error"
                      ? "Action Needed"
                      : "Awaiting Action"}
              </Text>
            </View>
          </View>
          <Text style={styles.descriptionText}>{card.description}</Text>
        </View>
      </View>

      {isVerify && status === "idle" && (
        <View style={styles.demoWarningBox}>
          <Text style={styles.demoWarningText}>
            Demo only: please upload sample documents, not your real Aadhaar or
            PAN.
          </Text>
        </View>
      )}

      {isAuth && status === "idle" && (
        <Text style={styles.authNoticeText}>
          Authorizing lets verified recruiters and placement officers contact
          your internship company to confirm it.
        </Text>
      )}

      {feedback && (
        <View
          style={[
            styles.feedbackBox,
            status === "confirmed"
              ? styles.feedbackSuccess
              : styles.feedbackNeutral,
          ]}
        >
          <Text
            style={[
              styles.feedbackText,
              status === "confirmed"
                ? styles.feedbackTextSuccess
                : styles.feedbackTextNeutral,
            ]}
          >
            {feedback}
          </Text>
        </View>
      )}

      {errorMessage && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{errorMessage}</Text>
          {errorMessage.includes("upload a sample file first") &&
            onOpenUpload && (
              <TouchableOpacity onPress={onOpenUpload} style={{ marginTop: 4 }}>
                <Text style={styles.uploadLinkText}>
                  Open Document Upload →
                </Text>
              </TouchableOpacity>
            )}
        </View>
      )}

      {status === "idle" && (
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[
              styles.confirmButton,
              isRevoke ? styles.revokeButton : styles.primaryButton,
            ]}
            onPress={handleConfirm}
          >
            <Text style={styles.confirmButtonText}>
              {card.button_text || "Confirm"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.cancelButton} onPress={handleCancel}>
            <Text style={styles.cancelButtonText}>Cancel</Text>
          </TouchableOpacity>
        </View>
      )}

      {status === "loading" && (
        <View style={styles.loadingRow}>
          <ActivityIndicator size="small" color="#4F46E5" />
          <Text style={styles.loadingText}>Processing confirmation...</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  cardContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    padding: 14,
    marginTop: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
  },
  iconCircle: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
  },
  iconText: {
    fontSize: 18,
  },
  titleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 6,
  },
  titleText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#0F172A",
    flex: 1,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "700",
  },
  descriptionText: {
    fontSize: 12,
    color: "#475569",
    marginTop: 4,
    lineHeight: 16,
  },
  demoWarningBox: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
    borderWidth: 1,
    borderRadius: 8,
    padding: 8,
    marginTop: 8,
  },
  demoWarningText: {
    fontSize: 11,
    color: "#92400E",
    fontWeight: "600",
  },
  authNoticeText: {
    fontSize: 11,
    color: "#64748B",
    marginTop: 6,
    lineHeight: 15,
  },
  feedbackBox: {
    marginTop: 8,
    padding: 8,
    borderRadius: 8,
  },
  feedbackSuccess: {
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  feedbackNeutral: {
    backgroundColor: "#F1F5F9",
  },
  feedbackText: {
    fontSize: 11,
  },
  feedbackTextSuccess: {
    color: "#065F46",
    fontWeight: "600",
  },
  feedbackTextNeutral: {
    color: "#475569",
  },
  errorBox: {
    backgroundColor: "#FEF2F2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: 8,
    padding: 8,
    marginTop: 8,
  },
  errorText: {
    fontSize: 11,
    color: "#B91C1C",
  },
  uploadLinkText: {
    fontSize: 11,
    color: "#4F46E5",
    fontWeight: "700",
  },
  buttonRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 12,
  },
  confirmButton: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryButton: {
    backgroundColor: "#4F46E5",
  },
  revokeButton: {
    backgroundColor: "#DC2626",
  },
  confirmButtonText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
  },
  cancelButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },
  cancelButtonText: {
    color: "#475569",
    fontSize: 12,
    fontWeight: "600",
  },
  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 10,
  },
  loadingText: {
    fontSize: 11,
    color: "#4F46E5",
    fontWeight: "600",
  },
});
