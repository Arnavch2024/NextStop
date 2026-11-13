import React, { useState } from "react";
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  StyleSheet,
  ScrollView,
} from "react-native";
import { Feather } from "@expo/vector-icons";
import {
  authorizeReferenceCheck,
  revokeReferenceCheck,
  InternshipRecord,
  ScoreResponse,
} from "@recruiting/shared";

interface MobileReferenceAuthModalProps {
  visible: boolean;
  onClose: () => void;
  token: string;
  baseUrl: string;
  internships: InternshipRecord[];
  isAuthorized: boolean;
  authorizedParty?: string | null;
  onSuccess: (score?: ScoreResponse, isAuthorized?: boolean) => void;
}

export function MobileReferenceAuthModal({
  visible,
  onClose,
  token,
  baseUrl,
  internships = [],
  isAuthorized,
  authorizedParty,
  onSuccess,
}: MobileReferenceAuthModalProps) {
  const [selectedInternshipId, setSelectedInternshipId] = useState<string>(
    internships[0]?.id || ""
  );
  const [selectedPartyType, setSelectedPartyType] = useState<string>(
    "Campus Placement Cell"
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const partyOptions = [
    "Campus Placement Cell",
    "Verified Recruiting Partner",
    "Internship Employer",
  ];

  async function handleAuthorize() {
    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const selectedIntern = internships.find(
        (i) => i.id === selectedInternshipId
      );
      const res = await authorizeReferenceCheck(baseUrl, token, {
        internship_id: selectedInternshipId || undefined,
        authorized_party: selectedPartyType,
        authorized_role: selectedIntern?.role || "Intern",
      });

      setSuccessMessage("Reference check authorized! +2 points added.");
      onSuccess(res.score, true);
      setTimeout(() => {
        onClose();
      }, 1400);
    } catch (err: any) {
      setError(err.message || "Failed to authorize reference check.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRevoke() {
    Alert.alert(
      "Revoke Authorization",
      "Revoking authorization will remove reference outreach permission and decrease your readiness score by 2 points. Continue?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Revoke",
          style: "destructive",
          onPress: async () => {
            setIsRevoking(true);
            setError(null);
            try {
              const res = await revokeReferenceCheck(baseUrl, token);
              setSuccessMessage("Authorization revoked. Score updated.");
              onSuccess(res.score, false);
              setTimeout(() => {
                onClose();
              }, 1200);
            } catch (err: any) {
              setError(err.message || "Failed to revoke authorization.");
            } finally {
              setIsRevoking(false);
            }
          },
        },
      ]
    );
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalContainer}>
          <ScrollView contentContainerStyle={styles.scrollContent}>
            {/* Header */}
            <View style={styles.headerRow}>
              <View style={styles.headerLeft}>
                <View style={styles.headerIconBadge}>
                  <Feather name="award" size={16} color="#4f46e5" />
                </View>
                <View>
                  <Text style={styles.headerTitle}>
                    Reference Check Authorization
                  </Text>
                  <Text style={styles.headerSubtitle}>
                    Internship employer verification (+2 points)
                  </Text>
                </View>
              </View>
              <TouchableOpacity
                onPress={onClose}
                style={styles.closeBtn}
                accessibilityLabel="Close"
              >
                <Feather name="x" size={16} color="#64748b" />
              </TouchableOpacity>
            </View>

            {/* Explanation Notice */}
            <View style={styles.infoBox}>
              <Text style={styles.infoText}>
                Authorizing allows verified recruiters and placement officers to
                contact your internship company to confirm your experience.
              </Text>
            </View>

            {/* Current Active Authorization status */}
            {isAuthorized && (
              <View style={styles.activeCard}>
                <View style={styles.activeCardHeader}>
                  <View style={{ flex: 1 }}>
                    <View
                      style={{
                        flexDirection: "row",
                        alignItems: "center",
                        gap: 5,
                        marginBottom: 4,
                      }}
                    >
                      <Feather name="check" size={13} color="#059669" />
                      <Text style={styles.activeCardTitle}>
                        Active Authorization
                      </Text>
                    </View>
                    <Text style={styles.activeCardParty}>
                      Party: {authorizedParty || "Campus Placement Cell"}
                    </Text>
                    <Text style={styles.activeCardNote}>
                      Permission active to contact employer.
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.revokeInlineBtn}
                    onPress={handleRevoke}
                    disabled={isRevoking}
                  >
                    {isRevoking ? (
                      <ActivityIndicator size="small" color="#DC2626" />
                    ) : (
                      <Text style={styles.revokeInlineText}>Revoke</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {/* Select Internship */}
            <Text style={styles.sectionLabel}>
              1. Select Internship Experience:
            </Text>
            {internships.length > 0 ? (
              <View style={styles.optionsList}>
                {internships.map((intn) => (
                  <TouchableOpacity
                    key={intn.id}
                    style={[
                      styles.optionCard,
                      selectedInternshipId === intn.id &&
                        styles.optionCardSelected,
                    ]}
                    onPress={() => setSelectedInternshipId(intn.id)}
                  >
                    <View style={styles.radioCircle}>
                      {selectedInternshipId === intn.id && (
                        <View style={styles.radioInner} />
                      )}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.optionTitle}>
                        {intn.role || "Intern"} at {intn.company}
                      </Text>
                      <Text style={styles.optionSubtitle}>
                        {intn.start_date || ""}{" "}
                        {intn.end_date ? `— ${intn.end_date}` : "— Ongoing"}
                      </Text>
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <View style={styles.noInternshipsBox}>
                <Text style={styles.noInternshipsText}>
                  No internships recorded yet. You can still authorize campus
                  placement cell outreach or add internships in chat.
                </Text>
              </View>
            )}

            {/* Select Authorized Party */}
            <Text style={styles.sectionLabel}>2. Select Authorized Party:</Text>
            <View style={styles.optionsList}>
              {partyOptions.map((party) => (
                <TouchableOpacity
                  key={party}
                  style={[
                    styles.optionCard,
                    selectedPartyType === party && styles.optionCardSelected,
                  ]}
                  onPress={() => setSelectedPartyType(party)}
                >
                  <View style={styles.radioCircle}>
                    {selectedPartyType === party && (
                      <View style={styles.radioInner} />
                    )}
                  </View>
                  <Text style={styles.optionTitle}>{party}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Success / Error Messages */}
            {successMessage && (
              <View style={styles.successBox}>
                <View
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <Feather name="check" size={13} color="#059669" />
                  <Text style={styles.successText}>{successMessage}</Text>
                </View>
              </View>
            )}

            {error && (
              <View style={styles.errorBox}>
                <View
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <Feather name="alert-circle" size={13} color="#dc2626" />
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              </View>
            )}

            {/* Submit Action */}
            <TouchableOpacity
              style={[
                styles.submitBtn,
                isSubmitting && styles.submitBtnDisabled,
              ]}
              onPress={handleAuthorize}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.submitBtnText}>
                  {isAuthorized
                    ? "Update Authorization"
                    : "Authorize Reference Check (+2)"}
                </Text>
              )}
            </TouchableOpacity>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "flex-end",
  },
  modalContainer: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "90%",
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  headerIconBadge: {
    width: 34,
    height: 34,
    borderRadius: 8,
    backgroundColor: "#eef2ff",
    borderWidth: 1,
    borderColor: "#c7d2fe",
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },
  headerSubtitle: {
    fontSize: 11,
    color: "#64748B",
  },
  closeBtn: {
    padding: 6,
  },
  closeBtnText: {
    fontSize: 16,
    color: "#94A3B8",
    fontWeight: "700",
  },
  infoBox: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
  },
  infoText: {
    fontSize: 11,
    color: "#475569",
    lineHeight: 16,
  },
  activeCard: {
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
  },
  activeCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  activeCardTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: "#065F46",
  },
  activeCardParty: {
    fontSize: 12,
    fontWeight: "600",
    color: "#0F172A",
    marginTop: 2,
  },
  activeCardNote: {
    fontSize: 10,
    color: "#047857",
    marginTop: 2,
  },
  revokeInlineBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#FECACA",
    backgroundColor: "#FEF2F2",
  },
  revokeInlineText: {
    fontSize: 11,
    color: "#DC2626",
    fontWeight: "700",
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: "#334155",
    marginBottom: 8,
  },
  optionsList: {
    gap: 8,
    marginBottom: 14,
  },
  optionCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    backgroundColor: "#FFFFFF",
  },
  optionCardSelected: {
    borderColor: "#4F46E5",
    backgroundColor: "#EEF2FF",
  },
  radioCircle: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: "#94A3B8",
    alignItems: "center",
    justifyContent: "center",
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#4F46E5",
  },
  optionTitle: {
    fontSize: 12,
    fontWeight: "600",
    color: "#0F172A",
  },
  optionSubtitle: {
    fontSize: 10,
    color: "#64748B",
    marginTop: 2,
  },
  noInternshipsBox: {
    padding: 12,
    backgroundColor: "#F8FAFC",
    borderRadius: 8,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  noInternshipsText: {
    fontSize: 11,
    color: "#64748B",
    lineHeight: 15,
  },
  successBox: {
    backgroundColor: "#ECFDF5",
    borderColor: "#A7F3D0",
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  successText: {
    fontSize: 12,
    color: "#065F46",
    fontWeight: "600",
  },
  errorBox: {
    backgroundColor: "#FEF2F2",
    borderColor: "#FECACA",
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  errorText: {
    fontSize: 12,
    color: "#B91C1C",
    fontWeight: "500",
  },
  submitBtn: {
    backgroundColor: "#4F46E5",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 4,
  },
  submitBtnDisabled: {
    backgroundColor: "#94A3B8",
  },
  submitBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
});
