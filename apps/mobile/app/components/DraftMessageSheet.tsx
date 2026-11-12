import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  StyleSheet,
  ScrollView,
  Linking,
  Platform,
} from "react-native";
import * as Clipboard from "expo-clipboard";
import { ContactCard, draftOutreach, ApiError } from "@recruiting/shared";
import { withApiFallback } from "../../lib/supabase";

interface DraftMessageSheetProps {
  visible: boolean;
  onClose: () => void;
  contact: ContactCard | null;
  token: string | null;
  showToast: (message: string) => void;
}

export function DraftMessageSheet({
  visible,
  onClose,
  contact,
  token,
  showToast,
}: DraftMessageSheetProps) {
  const [channel, setChannel] = useState<"email" | "linkedin">("email");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (!visible || !contact || !token) {
      setSubject("");
      setBody("");
      setError(null);
      return;
    }

    let isMounted = true;

    async function fetchDraft() {
      setIsLoading(true);
      setError(null);
      setIsCopied(false);

      try {
        const response = await withApiFallback((url) =>
          draftOutreach(url, token!, {
            contact_id: contact!.id,
            channel,
          })
        );

        if (isMounted) {
          setSubject(response.subject || "");
          setBody(response.body || "");
        }
      } catch (err: any) {
        if (!isMounted) return;
        if (err instanceof ApiError && err.status === 429) {
          setError(
            "Rate limit reached. Please wait a moment before trying again."
          );
        } else {
          setError(
            err.message ||
              "Failed to generate outreach draft. Please try again."
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchDraft();

    return () => {
      isMounted = false;
    };
  }, [visible, contact, token, channel]);

  if (!contact) return null;

  async function handleCopy() {
    try {
      const textToCopy =
        channel === "email" && subject
          ? `Subject: ${subject}\n\n${body}`
          : body;
      await Clipboard.setStringAsync(textToCopy);
      setIsCopied(true);
      showToast(
        channel === "email" ? "Email draft copied!" : "LinkedIn note copied!"
      );
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      showToast("Failed to copy to clipboard");
    }
  }

  function handleMailto() {
    const emailTo = contact?.email || "";
    const encodedSubject = encodeURIComponent(subject);
    const encodedBody = encodeURIComponent(body);
    const mailtoUrl = `mailto:${emailTo}?subject=${encodedSubject}&body=${encodedBody}`;
    Linking.openURL(mailtoUrl).catch(() => {
      showToast("Could not open mail app");
    });
  }

  function handleOpenLinkedIn() {
    if (contact?.linkedin_url) {
      Linking.openURL(contact.linkedin_url).catch(() => {
        showToast("Could not open LinkedIn URL");
      });
    }
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          {/* Header */}
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.headerSubtitle}>DRAFT MESSAGE</Text>
              <Text style={styles.headerTitle}>{contact.name}</Text>
              <Text style={styles.headerCompany}>
                {contact.title || "Recruiter"}
                {contact.company_name ? ` at ${contact.company_name}` : ""}
              </Text>
            </View>
            <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
              <Text style={styles.closeBtnText}>✕</Text>
            </TouchableOpacity>
          </View>

          {/* Channel Tabs */}
          <View style={styles.tabRow}>
            <TouchableOpacity
              style={[
                styles.tabBtn,
                channel === "email" && styles.tabBtnActive,
              ]}
              onPress={() => setChannel("email")}
            >
              <Text
                style={[
                  styles.tabBtnText,
                  channel === "email" && styles.tabBtnTextActive,
                ]}
              >
                ✉ Email Draft
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.tabBtn,
                channel === "linkedin" && styles.tabBtnActive,
              ]}
              onPress={() => setChannel("linkedin")}
            >
              <Text
                style={[
                  styles.tabBtnText,
                  channel === "linkedin" && styles.tabBtnTextActive,
                ]}
              >
                in LinkedIn Note
              </Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.scrollArea}>
            {/* Mandatory Safety Notice */}
            <View style={styles.warningBox}>
              <Text style={styles.warningIcon}>🛡</Text>
              <Text style={styles.warningText}>
                Review before sending. Nothing is sent for you.
              </Text>
            </View>

            {isLoading ? (
              <View style={styles.loadingBox}>
                <ActivityIndicator size="small" color="#4f46e5" />
                <Text style={styles.loadingText}>
                  Generating personalized draft...
                </Text>
              </View>
            ) : error ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorTitle}>Error generating draft</Text>
                <Text style={styles.errorMessage}>{error}</Text>
                <TouchableOpacity
                  style={styles.retryBtn}
                  onPress={() => setChannel((c) => c)}
                >
                  <Text style={styles.retryBtnText}>Try Again</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <View style={styles.editorBox}>
                {channel === "email" && (
                  <View style={styles.fieldGroup}>
                    <Text style={styles.fieldLabel}>Subject</Text>
                    <TextInput
                      style={styles.subjectInput}
                      value={subject}
                      onChangeText={setSubject}
                      placeholder="Subject line"
                      placeholderTextColor="#94a3b8"
                    />
                  </View>
                )}

                <View style={styles.fieldGroup}>
                  <View style={styles.fieldHeader}>
                    <Text style={styles.fieldLabel}>
                      {channel === "email"
                        ? "Message Body"
                        : "LinkedIn Note (under 300 chars)"}
                    </Text>
                    {channel === "linkedin" && (
                      <Text
                        style={[
                          styles.charCount,
                          body.length > 300 && styles.charCountOver,
                        ]}
                      >
                        {body.length}/300
                      </Text>
                    )}
                  </View>
                  <TextInput
                    style={styles.bodyInput}
                    value={body}
                    onChangeText={setBody}
                    multiline
                    numberOfLines={channel === "email" ? 7 : 4}
                    placeholder="Draft message body..."
                    placeholderTextColor="#94a3b8"
                    textAlignVertical="top"
                  />
                </View>

                {channel === "linkedin" && contact.linkedin_url && (
                  <TouchableOpacity
                    style={styles.linkedInLinkBtn}
                    onPress={handleOpenLinkedIn}
                  >
                    <Text style={styles.linkedInLinkText}>
                      🔗 Open LinkedIn profile in browser
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
            )}
          </ScrollView>

          {/* Footer Actions */}
          <View style={styles.footer}>
            <TouchableOpacity style={styles.cancelBtn} onPress={onClose}>
              <Text style={styles.cancelBtnText}>Close</Text>
            </TouchableOpacity>

            <View style={styles.actionRow}>
              <TouchableOpacity
                style={[
                  styles.copyBtn,
                  (!body || isLoading) && styles.btnDisabled,
                ]}
                onPress={handleCopy}
                disabled={!body || isLoading}
              >
                <Text style={styles.copyBtnText}>
                  {isCopied ? "✓ Copied!" : "📋 Copy"}
                </Text>
              </TouchableOpacity>

              {channel === "email" && (
                <TouchableOpacity
                  style={[
                    styles.mailtoBtn,
                    (!body || isLoading) && styles.btnDisabled,
                  ]}
                  onPress={handleMailto}
                  disabled={!body || isLoading}
                >
                  <Text style={styles.mailtoBtnText}>✉ mailto</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#ffffff",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "85%",
    paddingBottom: Platform.OS === "ios" ? 28 : 16,
  },
  header: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    paddingTop: 18,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#f1f5f9",
  },
  headerSubtitle: {
    fontSize: 10,
    fontWeight: "700",
    color: "#4f46e5",
    letterSpacing: 0.5,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0f172a",
    marginTop: 2,
  },
  headerCompany: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 1,
  },
  closeBtn: {
    padding: 6,
  },
  closeBtnText: {
    fontSize: 18,
    color: "#94a3b8",
  },
  tabRow: {
    flexDirection: "row",
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#f1f5f9",
  },
  tabBtn: {
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
    marginRight: 8,
  },
  tabBtnActive: {
    borderBottomColor: "#4f46e5",
  },
  tabBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#64748b",
  },
  tabBtnTextActive: {
    color: "#4f46e5",
  },
  scrollArea: {
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  warningBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fef3c7",
    borderWidth: 1,
    borderColor: "#fde68a",
    borderRadius: 10,
    padding: 10,
    marginBottom: 12,
  },
  warningIcon: {
    fontSize: 14,
    marginRight: 6,
  },
  warningText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#92400e",
    flex: 1,
  },
  loadingBox: {
    alignItems: "center",
    paddingVertical: 32,
  },
  loadingText: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 8,
  },
  errorBox: {
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fecaca",
    borderRadius: 10,
    padding: 12,
    marginVertical: 12,
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: "#b91c1c",
  },
  errorMessage: {
    fontSize: 11,
    color: "#475569",
    marginTop: 4,
  },
  retryBtn: {
    backgroundColor: "#dc2626",
    borderRadius: 6,
    paddingVertical: 6,
    paddingHorizontal: 12,
    alignSelf: "flex-start",
    marginTop: 8,
  },
  retryBtnText: {
    fontSize: 11,
    fontWeight: "600",
    color: "#ffffff",
  },
  editorBox: {
    marginBottom: 16,
  },
  fieldGroup: {
    marginBottom: 12,
  },
  fieldHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  fieldLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: "#64748b",
    marginBottom: 4,
  },
  charCount: {
    fontSize: 10,
    color: "#94a3b8",
  },
  charCountOver: {
    color: "#dc2626",
    fontWeight: "700",
  },
  subjectInput: {
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 8,
    backgroundColor: "#f8fafc",
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 12,
    color: "#0f172a",
  },
  bodyInput: {
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 8,
    backgroundColor: "#f8fafc",
    padding: 10,
    fontSize: 12,
    color: "#0f172a",
    minHeight: 100,
  },
  linkedInLinkBtn: {
    marginTop: 4,
    marginBottom: 8,
  },
  linkedInLinkText: {
    fontSize: 11,
    color: "#4f46e5",
    fontWeight: "600",
  },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: 8,
    paddingHorizontal: 20,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
  },
  cancelBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  cancelBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#64748b",
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  copyBtn: {
    backgroundColor: "#f1f5f9",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  copyBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#1e293b",
  },
  mailtoBtn: {
    backgroundColor: "#4f46e5",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
  },
  mailtoBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#ffffff",
  },
  btnDisabled: {
    opacity: 0.5,
  },
});
