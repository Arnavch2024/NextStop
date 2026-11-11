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
import * as DocumentPicker from "expo-document-picker";
import {
  uploadResume,
  verifyMock,
  revokeVerifyMock,
  DocumentRecord,
  ScoreResponse,
} from "@recruiting/shared";

interface MobilePreVerifyModalProps {
  visible: boolean;
  onClose: () => void;
  token: string;
  baseUrl: string;
  documents?: DocumentRecord[];
  onSuccess: (score?: ScoreResponse) => void;
}

export function MobilePreVerifyModal({
  visible,
  onClose,
  token,
  baseUrl,
  documents = [],
  onSuccess,
}: MobilePreVerifyModalProps) {
  const [selectedFile, setSelectedFile] = useState<{
    uri: string;
    name: string;
    mimeType?: string;
    size?: number;
  } | null>(null);
  const [docType, setDocType] = useState<"aadhaar" | "pan" | "other">(
    "aadhaar"
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const verifiedDoc = documents.find((d) => d.verified_flag);
  const hasUploadedDocs = documents.length > 0;
  const maskedTail = verifiedDoc?.masked_id_tail;

  async function handlePickFile() {
    setError(null);
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          "application/pdf",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "application/msword",
        ],
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets || result.assets.length === 0) {
        return;
      }

      const asset = result.assets[0];
      const MAX_BYTES = 5 * 1024 * 1024;
      if (asset.size && asset.size > MAX_BYTES) {
        setError("File exceeds maximum allowed size of 5 MB.");
        return;
      }

      setSelectedFile({
        uri: asset.uri,
        name: asset.name,
        mimeType: asset.mimeType,
        size: asset.size,
      });
    } catch (err: any) {
      setError(err.message || "Failed to pick file.");
    }
  }

  async function handleUploadAndVerify() {
    if (!selectedFile) {
      setError("Please pick a sample document first.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      // 1. Upload sample file safely
      const filePayload = {
        uri: selectedFile.uri,
        name: selectedFile.name,
        type: selectedFile.mimeType || "application/pdf",
      };

      const uploadRes = await uploadResume(
        baseUrl,
        filePayload,
        selectedFile.name,
        token
      );

      // 2. Automatically trigger mock verification
      const verifyRes = await verifyMock(baseUrl, token, {
        document_id: uploadRes.document_id,
        document_type: docType,
      });

      setSuccessMessage("Sample document pre-verified! +2 points added.");
      onSuccess(verifyRes.score);
      setSelectedFile(null);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err: any) {
      if (err.status === 404) {
        setError("Verification is not enabled in this environment.");
      } else {
        setError(err.message || "Failed to complete demo verification.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRevoke() {
    Alert.alert(
      "Remove Documents",
      "Are you sure you want to remove your documents and revoke verification?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: async () => {
            setIsRevoking(true);
            setError(null);
            try {
              const res = await revokeVerifyMock(baseUrl, token);
              setSuccessMessage("Documents removed and verification revoked.");
              onSuccess(res.score);
              setTimeout(() => {
                onClose();
              }, 1200);
            } catch (err: any) {
              setError(err.message || "Failed to remove documents.");
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
                <Text style={styles.headerIcon}>🛡️</Text>
                <View>
                  <Text style={styles.headerTitle}>
                    Document Pre-Verification
                  </Text>
                  <Text style={styles.headerSubtitle}>
                    Demo verification (mocked)
                  </Text>
                </View>
              </View>
              <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
                <Text style={styles.closeBtnText}>✕</Text>
              </TouchableOpacity>
            </View>

            {/* Current Status Chips */}
            <View style={styles.statusChipsRow}>
              <Text style={styles.statusLabel}>Current Status:</Text>
              {verifiedDoc ? (
                <View style={[styles.chip, styles.chipVerified]}>
                  <Text style={styles.chipVerifiedText}>
                    ✓ Verified (mocked)
                  </Text>
                </View>
              ) : hasUploadedDocs ? (
                <View style={[styles.chip, styles.chipUploaded]}>
                  <Text style={styles.chipUploadedText}>Uploaded</Text>
                </View>
              ) : (
                <View style={[styles.chip, styles.chipPending]}>
                  <Text style={styles.chipPendingText}>Not verified</Text>
                </View>
              )}
            </View>

            {/* Masked tail */}
            {maskedTail && (
              <View style={styles.maskedBox}>
                <Text style={styles.maskedLabel}>Masked ID Identifier:</Text>
                <Text style={styles.maskedValue}>{maskedTail}</Text>
              </View>
            )}

            {/* Warning Banner */}
            <View style={styles.warningBox}>
              <Text style={styles.warningTitle}>⚠️ Demo only:</Text>
              <Text style={styles.warningText}>
                Please upload sample documents, not your real Aadhaar or PAN.
              </Text>
              <Text style={styles.warningSubtext}>
                This environment runs mocked verification for MVP testing. Never
                upload authentic government-issued identity documents.
              </Text>
            </View>

            {/* Plain-Language Explanation */}
            <View style={styles.infoBox}>
              <Text style={styles.infoTitle}>📋 Privacy & Data Notice</Text>
              <Text style={styles.infoItem}>
                • <Text style={{ fontWeight: "700" }}>What is read:</Text> Only
                document MIME type (PDF/Word) and file size to ensure valid
                upload. The application never reads file contents or ID numbers.
              </Text>
              <Text style={styles.infoItem}>
                • <Text style={{ fontWeight: "700" }}>What is stored:</Text>{" "}
                Document type, verification status, timestamp, and a masked tail
                identifier (e.g. XXXX-XXXX-1234) provided by the verification
                service.
              </Text>
              <Text style={styles.infoItem}>
                • <Text style={{ fontWeight: "700" }}>Your consent:</Text>{" "}
                Revoking removes all document records, clears masked values, and
                updates your readiness score.
              </Text>
            </View>

            {/* Document Type Selector */}
            <Text style={styles.inputLabel}>Document Type (Sample):</Text>
            <View style={styles.docTypeRow}>
              {(["aadhaar", "pan", "other"] as const).map((t) => (
                <TouchableOpacity
                  key={t}
                  style={[
                    styles.docTypeButton,
                    docType === t && styles.docTypeButtonSelected,
                  ]}
                  onPress={() => setDocType(t)}
                >
                  <Text
                    style={[
                      styles.docTypeText,
                      docType === t && styles.docTypeTextSelected,
                    ]}
                  >
                    {t === "aadhaar"
                      ? "Aadhaar"
                      : t === "pan"
                        ? "PAN"
                        : "Other"}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* File Picker */}
            <TouchableOpacity style={styles.pickerBox} onPress={handlePickFile}>
              <Text style={styles.pickerIcon}>📄</Text>
              <Text style={styles.pickerTitle}>
                {selectedFile ? selectedFile.name : "Choose Sample Document"}
              </Text>
              <Text style={styles.pickerSubtitle}>
                {selectedFile
                  ? `${((selectedFile.size || 0) / 1024).toFixed(0)} KB • Tap to change`
                  : "PDF or DOCX, max 5 MB"}
              </Text>
            </TouchableOpacity>

            {/* Success / Error Messages */}
            {successMessage && (
              <View style={styles.successBox}>
                <Text style={styles.successText}>✓ {successMessage}</Text>
              </View>
            )}

            {error && (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>✕ {error}</Text>
              </View>
            )}

            {/* Action Buttons */}
            <View style={styles.actionRow}>
              <TouchableOpacity
                style={[
                  styles.uploadBtn,
                  (!selectedFile || isSubmitting) && styles.uploadBtnDisabled,
                ]}
                onPress={handleUploadAndVerify}
                disabled={!selectedFile || isSubmitting}
              >
                {isSubmitting ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.uploadBtnText}>
                    Upload & Mock Verify (+2)
                  </Text>
                )}
              </TouchableOpacity>
            </View>

            {/* Remove my documents action */}
            {hasUploadedDocs && (
              <TouchableOpacity
                style={styles.revokeBtn}
                onPress={handleRevoke}
                disabled={isRevoking}
              >
                {isRevoking ? (
                  <ActivityIndicator size="small" color="#DC2626" />
                ) : (
                  <Text style={styles.revokeBtnText}>
                    🗑️ Remove my documents & revoke verification
                  </Text>
                )}
              </TouchableOpacity>
            )}
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
    marginBottom: 12,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  headerIcon: {
    fontSize: 24,
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
  statusChipsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 12,
  },
  statusLabel: {
    fontSize: 12,
    color: "#64748B",
    fontWeight: "600",
  },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 12,
  },
  chipVerified: {
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  chipVerifiedText: {
    color: "#065F46",
    fontSize: 11,
    fontWeight: "700",
  },
  chipUploaded: {
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
  },
  chipUploadedText: {
    color: "#1D4ED8",
    fontSize: 11,
    fontWeight: "700",
  },
  chipPending: {
    backgroundColor: "#F1F5F9",
  },
  chipPendingText: {
    color: "#64748B",
    fontSize: 11,
    fontWeight: "600",
  },
  maskedBox: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 10,
    padding: 10,
    marginBottom: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  maskedLabel: {
    fontSize: 11,
    color: "#64748B",
  },
  maskedValue: {
    fontSize: 12,
    fontWeight: "700",
    fontFamily: "monospace",
    color: "#0F172A",
  },
  warningBox: {
    backgroundColor: "#FFFBEB",
    borderColor: "#FDE68A",
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  warningTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: "#92400E",
  },
  warningText: {
    fontSize: 12,
    color: "#92400E",
    fontWeight: "600",
    marginTop: 2,
  },
  warningSubtext: {
    fontSize: 10,
    color: "#B45309",
    marginTop: 4,
    lineHeight: 14,
  },
  infoBox: {
    backgroundColor: "#F8FAFC",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
    gap: 6,
  },
  infoTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: "#334155",
    marginBottom: 2,
  },
  infoItem: {
    fontSize: 11,
    color: "#475569",
    lineHeight: 15,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#334155",
    marginBottom: 6,
  },
  docTypeRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 14,
  },
  docTypeButton: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#CBD5E1",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
  },
  docTypeButtonSelected: {
    borderColor: "#4F46E5",
    backgroundColor: "#EEF2FF",
  },
  docTypeText: {
    fontSize: 12,
    color: "#475569",
    fontWeight: "600",
  },
  docTypeTextSelected: {
    color: "#4F46E5",
    fontWeight: "700",
  },
  pickerBox: {
    borderWidth: 1.5,
    borderColor: "#CBD5E1",
    borderStyle: "dashed",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    marginBottom: 14,
  },
  pickerIcon: {
    fontSize: 24,
    marginBottom: 4,
  },
  pickerTitle: {
    fontSize: 13,
    fontWeight: "600",
    color: "#0F172A",
  },
  pickerSubtitle: {
    fontSize: 10,
    color: "#64748B",
    marginTop: 2,
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
  actionRow: {
    marginTop: 4,
  },
  uploadBtn: {
    backgroundColor: "#4F46E5",
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  uploadBtnDisabled: {
    backgroundColor: "#94A3B8",
  },
  uploadBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "700",
  },
  revokeBtn: {
    marginTop: 12,
    paddingVertical: 10,
    alignItems: "center",
  },
  revokeBtnText: {
    color: "#DC2626",
    fontSize: 12,
    fontWeight: "600",
  },
});
