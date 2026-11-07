import React, { useState, useEffect, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  StyleSheet,
  SafeAreaView,
  Modal,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { Audio } from "expo-av";
import * as DocumentPicker from "expo-document-picker";
import { getMobileSupabaseClient, API_BASE_URL } from "../lib/supabase";
import {
  chat,
  transcribeAudio,
  uploadResume,
  AgentStep,
  RecordRef,
  RawEvent,
  ResumeResponse,
} from "@recruiting/shared";

interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  steps?: AgentStep[];
  records?: RecordRef[];
  resumeSummary?: ResumeResponse;
  timestamp: string;
}

export default function ChatScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string>("User");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Voice recording state
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  // Resume upload state
  const [isConsentVisible, setIsConsentVisible] = useState(false);
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);

  // Realtime cross-device toast
  const [crossDeviceToast, setCrossDeviceToast] = useState<string | null>(null);

  const flatListRef = useRef<FlatList>(null);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  function showToast(text: string) {
    setCrossDeviceToast(text);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = setTimeout(() => {
      setCrossDeviceToast(null);
    }, 4500);
  }

  // 1. Authenticate & fetch user profile
  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setSessionToken(session.access_token);
      setUserId(session.user.id);

      const { data: profile } = await supabase
        .from("profiles")
        .select("*")
        .eq("id", session.user.id)
        .single();

      if (!profile || !profile.role) {
        router.replace("/onboarding");
        return;
      }

      setRole(profile.role);
      setDisplayName(
        profile.display_name || session.user.email?.split("@")[0] || "User"
      );

      // Load initial message history
      const { data: events } = await supabase
        .from("raw_events")
        .select("*")
        .eq("actor_id", session.user.id)
        .in("source", ["user_message", "agent_message"])
        .order("created_at", { ascending: true })
        .limit(100);

      if (events) {
        setMessages(
          events.map((ev: RawEvent) => ({
            id: ev.id,
            sender: ev.source === "user_message" ? "user" : "agent",
            text: ev.payload?.message || "",
            timestamp: ev.created_at,
          }))
        );
      }
    });
  }, [router, supabase]);

  // 2. Supabase Realtime Subscription for cross-device sync
  useEffect(() => {
    if (!userId) return;

    // Messages sync
    const chatChannel = supabase
      .channel(`mobile_raw_events_${userId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "raw_events",
          filter: `actor_id=eq.${userId}`,
        },
        (payload) => {
          const newEvent = payload.new as RawEvent;
          if (
            newEvent.source === "user_message" ||
            newEvent.source === "agent_message"
          ) {
            setMessages((prev) => {
              if (prev.some((m) => m.id === newEvent.id)) return prev;
              return [
                ...prev,
                {
                  id: newEvent.id,
                  sender: newEvent.source === "user_message" ? "user" : "agent",
                  text: newEvent.payload?.message || "",
                  timestamp: newEvent.created_at,
                },
              ];
            });
          }
        }
      )
      .subscribe();

    // Score events sync -> "Updated from your laptop"
    const scoreChannel = supabase
      .channel(`mobile_score_events_${userId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "score_events",
          filter: `profile_id=eq.${userId}`,
        },
        (payload) => {
          const sc = (payload.new as any)?.score;
          showToast(
            sc !== undefined
              ? `Score updated to ${sc} from your laptop`
              : "Score updated from your laptop"
          );
        }
      )
      .subscribe();

    // Profile table updates
    const profileChannel = supabase
      .channel(`mobile_profile_events_${userId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "education",
          filter: `profile_id=eq.${userId}`,
        },
        () => showToast("Profile updated from your laptop")
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "internships",
          filter: `profile_id=eq.${userId}`,
        },
        () => showToast("Profile updated from your laptop")
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "skills",
          filter: `profile_id=eq.${userId}`,
        },
        () => showToast("Profile updated from your laptop")
      )
      .subscribe();

    return () => {
      supabase.removeChannel(chatChannel);
      supabase.removeChannel(scoreChannel);
      supabase.removeChannel(profileChannel);
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, [userId, supabase]);

  // Clean up audio on unmount
  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (recording) {
        recording.stopAndUnloadAsync().catch(() => {});
      }
    };
  }, [recording]);

  async function handleSend(overrideText?: string) {
    const text = (overrideText ?? inputText).trim();
    if (!text || isSending || !sessionToken) return;

    if (!overrideText) {
      setInputText("");
    }
    setIsSending(true);

    const tempUserId = `user-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: tempUserId,
        sender: "user",
        text,
        timestamp: new Date().toISOString(),
      },
    ]);

    try {
      const response = await chat(API_BASE_URL, text, sessionToken);

      const agentId = `agent-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: agentId,
          sender: "agent",
          text: response.reply,
          steps: response.steps,
          records: response.records_created,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: "agent",
          text: `Error connecting to agent: ${err.message || "Check connection."}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  // 3. Voice Recording via expo-av
  async function startRecording() {
    setVoiceError(null);
    if (!sessionToken) {
      setVoiceError("Session not ready.");
      return;
    }

    try {
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        setVoiceError(
          "Microphone permission denied. Please allow microphone access."
        );
        Alert.alert(
          "Permission Denied",
          "Microphone access is required for voice input."
        );
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const newRecording = new Audio.Recording();
      await newRecording.prepareToRecordAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      await newRecording.startAsync();

      setRecording(newRecording);
      setIsRecording(true);
      setRecordingSeconds(0);

      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      setVoiceError(err.message || "Could not start audio recording.");
      setIsRecording(false);
    }
  }

  async function stopRecording() {
    if (!recording) return;

    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }

    setIsRecording(false);
    setIsTranscribing(true);

    try {
      await recording.stopAndUnloadAsync();
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
      const uri = recording.getURI();
      setRecording(null);

      if (!uri) {
        setVoiceError("No audio captured.");
        setIsTranscribing(false);
        return;
      }

      const audioFile = {
        uri,
        name: "voice_note.m4a",
        type: "audio/m4a",
      };

      const res = await transcribeAudio(
        API_BASE_URL,
        audioFile,
        "voice_note.m4a",
        sessionToken!
      );

      if (res.text && res.text.trim()) {
        await handleSend(res.text.trim());
      } else {
        setVoiceError("No speech detected.");
      }
    } catch (err: any) {
      setVoiceError(err.message || "Voice transcription failed.");
    } finally {
      setIsTranscribing(false);
      setRecording(null);
    }
  }

  function toggleVoiceRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  // 4. Resume Upload via DocumentPicker
  function handleOpenResumePicker() {
    setResumeError(null);
    setIsConsentVisible(true);
  }

  async function handleConsentConfirm() {
    setIsConsentVisible(false);
    if (!sessionToken) return;

    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: [
          "application/pdf",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        copyToCacheDirectory: true,
      });

      if (res.canceled || !res.assets || res.assets.length === 0) {
        return;
      }

      const asset = res.assets[0];

      // Validate 5 MB
      const MAX_BYTES = 5 * 1024 * 1024;
      if (asset.size && asset.size > MAX_BYTES) {
        setResumeError(
          `Resume exceeds 5 MB limit (${(asset.size / 1024 / 1024).toFixed(1)} MB).`
        );
        Alert.alert(
          "File Too Large",
          "Please select a resume smaller than 5 MB."
        );
        return;
      }

      setIsUploadingResume(true);

      // Optimistic user bubble
      setMessages((prev) => [
        ...prev,
        {
          id: `user-resume-${Date.now()}`,
          sender: "user",
          text: `Uploaded resume: ${asset.name}`,
          timestamp: new Date().toISOString(),
        },
      ]);

      const filePayload = {
        uri: asset.uri,
        name: asset.name,
        type: asset.mimeType || "application/pdf",
      };

      const summary = await uploadResume(
        API_BASE_URL,
        filePayload,
        asset.name,
        sessionToken
      );

      setMessages((prev) => [
        ...prev,
        {
          id: `agent-resume-${Date.now()}`,
          sender: "agent",
          text: `I've analyzed your resume "${asset.name}". Your readiness score is now ${summary.score.score}/100.`,
          records: summary.records_created,
          resumeSummary: summary,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err: any) {
      setResumeError(err.message || "Failed to upload resume.");
      Alert.alert("Upload Failed", err.message || "Could not process resume.");
    } finally {
      setIsUploadingResume(false);
    }
  }

  function handleFixSomething(summary: ResumeResponse) {
    const missing = summary.missing_fields?.length
      ? summary.missing_fields.join(", ")
      : "details";
    setInputText(`I want to fix: ${missing}. Details: `);
  }

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60)
      .toString()
      .padStart(2, "0");
    const s = (secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.container}
      >
        {/* Realtime Sync Toast */}
        {crossDeviceToast && (
          <View style={styles.toastContainer}>
            <Text style={styles.toastIcon}>💻</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.toastTitle}>{crossDeviceToast}</Text>
              <Text style={styles.toastSubtitle}>Synced live from laptop</Text>
            </View>
            <TouchableOpacity onPress={() => setCrossDeviceToast(null)}>
              <Text style={styles.toastClose}>✕</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Error Bar */}
        {(voiceError || resumeError) && (
          <View style={styles.errorBar}>
            <Text style={styles.errorText}>{voiceError || resumeError}</Text>
            <TouchableOpacity
              onPress={() => {
                setVoiceError(null);
                setResumeError(null);
              }}
            >
              <Text style={styles.errorClose}>✕</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>Recruiting Assistant</Text>
            <Text style={styles.headerSubtitle}>
              {displayName} •{" "}
              <Text style={styles.roleText}>{role?.replace("_", " ")}</Text>
            </Text>
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            {role === "student" && (
              <TouchableOpacity
                onPress={() => router.push("/(tabs)/home")}
                style={styles.dashboardHeaderBtn}
              >
                <Text style={styles.dashboardHeaderText}>Dashboard</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity onPress={handleSignOut} style={styles.signOutBtn}>
              <Text style={styles.signOutText}>Sign Out</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Message List */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messageList}
          onContentSizeChange={() =>
            flatListRef.current?.scrollToEnd({ animated: true })
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>🤖</Text>
              <Text style={styles.emptyTitle}>
                Welcome to your Recruiting Assistant!
              </Text>
              <Text style={styles.emptySubtitle}>
                Type or speak your details naturally, or tap &ldquo;Add my
                resume&rdquo; to extract your profile without filling forms.
              </Text>
              <View style={styles.emptyActions}>
                <TouchableOpacity
                  style={styles.emptyBtn}
                  onPress={handleOpenResumePicker}
                >
                  <Text style={styles.emptyBtnText}>📄 Add my resume</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.emptyBtn, styles.emptyBtnOutline]}
                  onPress={toggleVoiceRecording}
                >
                  <Text style={styles.emptyBtnOutlineText}>
                    🎤 Speak via Voice
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          }
          renderItem={({ item }) => {
            const isUser = item.sender === "user";
            const isExpanded = expandedId === item.id;
            const hasStepsOrRecords =
              (item.steps && item.steps.length > 0) ||
              (item.records && item.records.length > 0);
            const summary = item.resumeSummary;

            return (
              <View
                style={[
                  styles.messageRow,
                  isUser ? styles.messageRowUser : styles.messageRowAgent,
                ]}
              >
                <View
                  style={[
                    styles.bubble,
                    isUser ? styles.bubbleUser : styles.bubbleAgent,
                  ]}
                >
                  <Text
                    style={
                      isUser ? styles.bubbleTextUser : styles.bubbleTextAgent
                    }
                  >
                    {item.text}
                  </Text>

                  {/* Parsed Summary Card */}
                  {summary && (
                    <View style={styles.summaryCard}>
                      <View style={styles.summaryHeader}>
                        <Text style={styles.summaryTitle}>
                          📄 Resume Summary Card
                        </Text>
                        <View style={styles.summaryScoreBadge}>
                          <Text style={styles.summaryScoreText}>
                            {summary.score.score}/100
                          </Text>
                        </View>
                      </View>

                      <Text style={styles.summarySub}>
                        {summary.records_created?.length || 0} record(s) synced
                      </Text>

                      {summary.missing_fields &&
                        summary.missing_fields.length > 0 && (
                          <View style={styles.missingBox}>
                            <Text style={styles.missingLabel}>
                              Missing to boost score:
                            </Text>
                            <Text style={styles.missingFields}>
                              {summary.missing_fields.join(", ")}
                            </Text>
                          </View>
                        )}

                      <View style={styles.summaryActions}>
                        <TouchableOpacity
                          style={styles.looksRightBtn}
                          onPress={() => router.push("/(tabs)/home")}
                        >
                          <Text style={styles.looksRightText}>
                            ✓ Looks right
                          </Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={styles.fixBtn}
                          onPress={() => handleFixSomething(summary)}
                        >
                          <Text style={styles.fixText}>Fix something</Text>
                        </TouchableOpacity>
                      </View>
                    </View>
                  )}

                  {/* Agent Steps */}
                  {hasStepsOrRecords && (
                    <View style={styles.stepsContainer}>
                      <TouchableOpacity
                        onPress={() =>
                          setExpandedId(isExpanded ? null : item.id)
                        }
                      >
                        <Text style={styles.stepsToggle}>
                          {item.records?.length
                            ? `✓ ${item.records.length} record(s) synced [Tap to view]`
                            : `⚙ ${item.steps?.length} agent step(s) [Tap to view]`}
                        </Text>
                      </TouchableOpacity>

                      {isExpanded && (
                        <View style={styles.stepsDetails}>
                          {item.records?.map((rec: RecordRef, i: number) => (
                            <Text key={i} style={styles.recText}>
                              ✓ {rec.op.toUpperCase()}: {rec.table}
                            </Text>
                          ))}
                        </View>
                      )}
                    </View>
                  )}
                </View>
              </View>
            );
          }}
        />

        {/* Loading States */}
        {isSending && (
          <View style={styles.typingIndicator}>
            <ActivityIndicator size="small" color="#4f46e5" />
            <Text style={styles.typingText}>
              Agent is updating structured records...
            </Text>
          </View>
        )}

        {isTranscribing && (
          <View
            style={[styles.typingIndicator, { backgroundColor: "#eef2ff" }]}
          >
            <ActivityIndicator size="small" color="#4f46e5" />
            <Text style={[styles.typingText, { color: "#4338ca" }]}>
              Transcribing your voice note...
            </Text>
          </View>
        )}

        {isUploadingResume && (
          <View
            style={[styles.typingIndicator, { backgroundColor: "#eef2ff" }]}
          >
            <ActivityIndicator size="small" color="#4f46e5" />
            <Text style={[styles.typingText, { color: "#4338ca" }]}>
              Reading and analyzing resume...
            </Text>
          </View>
        )}

        {/* Recording Overlay Bar */}
        {isRecording && (
          <View style={styles.recordingBar}>
            <View style={styles.recordingDot} />
            <Text style={styles.recordingText}>
              Recording: {formatTimer(recordingSeconds)}
            </Text>
            <TouchableOpacity
              style={styles.stopRecordingBtn}
              onPress={stopRecording}
            >
              <Text style={styles.stopRecordingText}>Finish & Send</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Composer */}
        <View style={styles.composer}>
          {/* Add My Resume Button */}
          <TouchableOpacity
            style={styles.resumeActionBtn}
            onPress={handleOpenResumePicker}
            disabled={isSending || isTranscribing || isUploadingResume}
          >
            <Text style={styles.resumeActionIcon}>📎</Text>
          </TouchableOpacity>

          {/* Voice Mic Button */}
          <TouchableOpacity
            style={[styles.voiceBtn, isRecording && styles.voiceBtnRecording]}
            onPress={toggleVoiceRecording}
            disabled={isSending || isTranscribing || isUploadingResume}
          >
            <Text style={styles.voiceBtnText}>{isRecording ? "⏹" : "🎤"}</Text>
          </TouchableOpacity>

          <TextInput
            style={styles.composerInput}
            value={inputText}
            onChangeText={setInputText}
            placeholder="Type your details (college, batch)..."
            placeholderTextColor="#94a3b8"
            editable={
              !isSending &&
              !isRecording &&
              !isTranscribing &&
              !isUploadingResume
            }
          />

          <TouchableOpacity
            style={[
              styles.sendBtn,
              (!inputText.trim() || isSending || isRecording) &&
                styles.sendBtnDisabled,
            ]}
            onPress={() => handleSend()}
            disabled={!inputText.trim() || isSending || isRecording}
          >
            <Text style={styles.sendBtnText}>&rarr;</Text>
          </TouchableOpacity>
        </View>

        {/* Consent Modal Sheet */}
        <Modal
          visible={isConsentVisible}
          transparent
          animationType="slide"
          onRequestClose={() => setIsConsentVisible(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <Text style={styles.modalIcon}>📄</Text>
              <Text style={styles.modalTitle}>Add your resume</Text>
              <Text style={styles.modalMessage}>
                We&rsquo;ll read this file to build your profile.
              </Text>

              <View style={styles.modalInfoBox}>
                <Text style={styles.modalInfoText}>• Max size: 5 MB</Text>
                <Text style={styles.modalInfoText}>• Formats: PDF or DOCX</Text>
                <Text style={styles.modalInfoText}>
                  • Structured records are generated automatically without
                  forms.
                </Text>
              </View>

              <View style={styles.modalActions}>
                <TouchableOpacity
                  style={styles.modalCancelBtn}
                  onPress={() => setIsConsentVisible(false)}
                >
                  <Text style={styles.modalCancelText}>Cancel</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={styles.modalConfirmBtn}
                  onPress={handleConsentConfirm}
                >
                  <Text style={styles.modalConfirmText}>
                    I Agree & Choose File
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#ffffff",
  },
  container: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
  toastContainer: {
    position: "absolute",
    top: 60,
    left: 16,
    right: 16,
    zIndex: 99,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#ffffff",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#c7d2fe",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  toastIcon: {
    fontSize: 20,
  },
  toastTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#1e1b4b",
  },
  toastSubtitle: {
    fontSize: 11,
    color: "#6366f1",
  },
  toastClose: {
    fontSize: 14,
    color: "#94a3b8",
    padding: 4,
  },
  errorBar: {
    backgroundColor: "#fef2f2",
    borderBottomWidth: 1,
    borderBottomColor: "#fecaca",
    paddingHorizontal: 16,
    paddingVertical: 8,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  errorText: {
    fontSize: 12,
    color: "#b91c1c",
    flex: 1,
  },
  errorClose: {
    fontSize: 14,
    color: "#b91c1c",
    paddingLeft: 8,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: "#ffffff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0f172a",
  },
  headerSubtitle: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 2,
  },
  roleText: {
    color: "#4f46e5",
    fontWeight: "600",
    textTransform: "capitalize",
  },
  dashboardHeaderBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    backgroundColor: "#ffffff",
  },
  dashboardHeaderText: {
    fontSize: 12,
    color: "#4f46e5",
    fontWeight: "600",
  },
  signOutBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: "#f1f5f9",
  },
  signOutText: {
    fontSize: 12,
    color: "#475569",
    fontWeight: "600",
  },
  messageList: {
    padding: 16,
    paddingBottom: 24,
  },
  emptyContainer: {
    alignItems: "center",
    marginVertical: 40,
    paddingHorizontal: 24,
  },
  emptyIcon: {
    fontSize: 44,
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0f172a",
    textAlign: "center",
    marginBottom: 6,
  },
  emptySubtitle: {
    fontSize: 12,
    color: "#64748b",
    textAlign: "center",
    lineHeight: 18,
    marginBottom: 16,
  },
  emptyActions: {
    flexDirection: "row",
    gap: 10,
  },
  emptyBtn: {
    backgroundColor: "#eef2ff",
    borderWidth: 1,
    borderColor: "#c7d2fe",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  emptyBtnText: {
    fontSize: 12,
    color: "#4338ca",
    fontWeight: "600",
  },
  emptyBtnOutline: {
    backgroundColor: "#ffffff",
    borderColor: "#e2e8f0",
  },
  emptyBtnOutlineText: {
    fontSize: 12,
    color: "#334155",
    fontWeight: "500",
  },
  messageRow: {
    marginVertical: 4,
    flexDirection: "row",
  },
  messageRowUser: {
    justifyContent: "flex-end",
  },
  messageRowAgent: {
    justifyContent: "flex-start",
  },
  bubble: {
    maxWidth: "85%",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 16,
  },
  bubbleUser: {
    backgroundColor: "#4f46e5",
    borderBottomRightRadius: 4,
  },
  bubbleAgent: {
    backgroundColor: "#ffffff",
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  bubbleTextUser: {
    color: "#ffffff",
    fontSize: 14,
    lineHeight: 20,
  },
  bubbleTextAgent: {
    color: "#0f172a",
    fontSize: 14,
    lineHeight: 20,
  },
  summaryCard: {
    marginTop: 10,
    backgroundColor: "#f5f3ff",
    borderWidth: 1,
    borderColor: "#ddd6fe",
    borderRadius: 12,
    padding: 12,
  },
  summaryHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  summaryTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#1e1b4b",
  },
  summaryScoreBadge: {
    backgroundColor: "#4f46e5",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
  },
  summaryScoreText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#ffffff",
  },
  summarySub: {
    fontSize: 11,
    color: "#6b7280",
    marginTop: 4,
  },
  missingBox: {
    marginTop: 8,
    backgroundColor: "#fffbeb",
    borderWidth: 1,
    borderColor: "#fef3c7",
    padding: 8,
    borderRadius: 8,
  },
  missingLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: "#92400e",
  },
  missingFields: {
    fontSize: 11,
    color: "#78350f",
    marginTop: 2,
  },
  summaryActions: {
    flexDirection: "row",
    gap: 8,
    marginTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#e0e7ff",
    paddingTop: 8,
  },
  looksRightBtn: {
    flex: 1,
    backgroundColor: "#4f46e5",
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: "center",
  },
  looksRightText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "700",
  },
  fixBtn: {
    flex: 1,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    paddingVertical: 7,
    borderRadius: 8,
    alignItems: "center",
  },
  fixText: {
    color: "#475569",
    fontSize: 12,
    fontWeight: "600",
  },
  stepsContainer: {
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
    paddingTop: 6,
  },
  stepsToggle: {
    fontSize: 11,
    color: "#4f46e5",
    fontWeight: "600",
  },
  stepsDetails: {
    marginTop: 4,
    backgroundColor: "#f8fafc",
    padding: 8,
    borderRadius: 8,
  },
  recText: {
    fontSize: 11,
    color: "#059669",
    fontWeight: "500",
  },
  typingIndicator: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  typingText: {
    fontSize: 12,
    color: "#64748b",
  },
  recordingBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#fef2f2",
    borderTopWidth: 1,
    borderTopColor: "#fecaca",
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  recordingDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#dc2626",
  },
  recordingText: {
    fontSize: 12,
    color: "#b91c1c",
    fontWeight: "700",
  },
  stopRecordingBtn: {
    backgroundColor: "#dc2626",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
  },
  stopRecordingText: {
    fontSize: 11,
    color: "#ffffff",
    fontWeight: "700",
  },
  composer: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#ffffff",
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
    gap: 8,
  },
  resumeActionBtn: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: "#f1f5f9",
    justifyContent: "center",
    alignItems: "center",
  },
  resumeActionIcon: {
    fontSize: 18,
  },
  voiceBtn: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: "#f1f5f9",
    justifyContent: "center",
    alignItems: "center",
  },
  voiceBtnRecording: {
    backgroundColor: "#fee2e2",
    borderWidth: 1,
    borderColor: "#ef4444",
  },
  voiceBtnText: {
    fontSize: 18,
  },
  composerInput: {
    flex: 1,
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
    color: "#0f172a",
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: "#4f46e5",
    justifyContent: "center",
    alignItems: "center",
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  sendBtnText: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "700",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: "#ffffff",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 36,
  },
  modalIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0f172a",
    marginBottom: 4,
  },
  modalMessage: {
    fontSize: 14,
    color: "#475569",
    lineHeight: 20,
    marginBottom: 12,
  },
  modalInfoBox: {
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    padding: 12,
    gap: 4,
    marginBottom: 20,
  },
  modalInfoText: {
    fontSize: 12,
    color: "#64748b",
  },
  modalActions: {
    flexDirection: "row",
    gap: 12,
  },
  modalCancelBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: "#f1f5f9",
    alignItems: "center",
  },
  modalCancelText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#475569",
  },
  modalConfirmBtn: {
    flex: 2,
    paddingVertical: 12,
    borderRadius: 10,
    backgroundColor: "#4f46e5",
    alignItems: "center",
  },
  modalConfirmText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#ffffff",
  },
});
