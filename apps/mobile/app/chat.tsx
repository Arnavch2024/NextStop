import React, { useState, useEffect, useRef, useMemo } from "react";
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
  Modal,
  Alert,
  ScrollView,
  useWindowDimensions,
} from "react-native";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Audio } from "expo-av";
import * as DocumentPicker from "expo-document-picker";
import {
  getMobileSupabaseClient,
  API_BASE_URL,
  withApiFallback,
  getEffectiveApiBaseUrl,
  saveCustomApiBaseUrl,
} from "../lib/supabase";
import {
  chat,
  transcribeAudio,
  uploadResume,
  saveContact,
  removeSavedContact,
  listContacts,
  health,
  AgentStep,
  RecordRef,
  RawEvent,
  ResumeResponse,
  ContactCard,
  ConfirmationCard,
  ApiError,
} from "@recruiting/shared";
import { MobileContactCard } from "./components/MobileContactCard";
import { DraftMessageSheet } from "./components/DraftMessageSheet";
import { MobileChatConfirmationCard } from "./components/MobileChatConfirmationCard";

interface QuickActionItem {
  label: string;
  prompt?: string;
  isResumeUpload?: boolean;
}

interface RoleChatConfig {
  icon: string;
  title: string;
  subtitle: string;
  placeholder: string;
  quickActions: QuickActionItem[];
}

interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  steps?: AgentStep[];
  records?: RecordRef[];
  contacts?: ContactCard[];
  cards?: ConfirmationCard[];
  resumeSummary?: ResumeResponse;
  timestamp: string;
}

export default function ChatScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const isSmallWidth = width < 375;

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

  // Saved contacts state
  const [savedContactIds, setSavedContactIds] = useState<
    Record<string, boolean>
  >({});
  const [savingContactId, setSavingContactId] = useState<string | null>(null);

  // Draft outreach modal state
  const [draftingContact, setDraftingContact] = useState<ContactCard | null>(
    null
  );

  // Realtime cross-device toast
  const [crossDeviceToast, setCrossDeviceToast] = useState<string | null>(null);

  // Server connection states
  const [currentBaseUrl, setCurrentBaseUrl] = useState<string>(API_BASE_URL);
  const [showServerModal, setShowServerModal] = useState<boolean>(false);
  const [customServerUrlInput, setCustomServerUrlInput] = useState<string>("");
  const [serverTestLoading, setServerTestLoading] = useState<boolean>(false);
  const [serverTestStatus, setServerTestStatus] = useState<string | null>(null);

  const flatListRef = useRef<FlatList>(null);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isSendingRef = useRef<boolean>(false);
  const isNearBottomRef = useRef<boolean>(true);

  useEffect(() => {
    getEffectiveApiBaseUrl().then((url) => {
      setCurrentBaseUrl(url);
      setCustomServerUrlInput(url);
    });
  }, []);

  async function handleTestServerConnection(urlToTest?: string) {
    const target = (urlToTest || customServerUrlInput || currentBaseUrl)
      .trim()
      .replace(/\/+$/, "");
    if (!target) return;
    setServerTestLoading(true);
    setServerTestStatus(null);
    try {
      const res = await health(target);
      if (res && res.status === "ok") {
        setServerTestStatus(
          `✅ Connected successfully! (v${res.version || "1.0"})`
        );
      } else {
        setServerTestStatus(
          "⚠️ Server responded but health status was not ok."
        );
      }
    } catch (err: any) {
      setServerTestStatus(
        `❌ Connection failed: ${err.message || "Network request failed"}`
      );
    } finally {
      setServerTestLoading(false);
    }
  }

  async function handleApplyServerUrl(newUrl?: string) {
    const target = (newUrl || customServerUrlInput || currentBaseUrl)
      .trim()
      .replace(/\/+$/, "");
    if (!target) return;
    await saveCustomApiBaseUrl(target);
    setCurrentBaseUrl(target);
    setCustomServerUrlInput(target);
    setShowServerModal(false);
    showToast(`Server URL set to: ${target}`);
  }

  const roleConfig: RoleChatConfig = useMemo(() => {
    switch (role) {
      case "placement_officer":
        return {
          icon: "🏛️",
          title: "Welcome, Placement Officer!",
          subtitle:
            "Import your student list, search students by batch or status, or find companies to invite for campus hiring.",
          placeholder: "Search students by batch, find hiring companies...",
          quickActions: [
            {
              label: "📥 Import student list (CSV)",
              prompt: "How can I import our student list via CSV?",
            },
            {
              label: "🏢 Companies to contact for BE Computer Science/IT/AI",
              prompt: "Companies to contact for BE Computer Science/IT/AI",
            },
          ],
        };
      case "company":
        return {
          icon: "🏢",
          title: "Welcome, Hiring Partner!",
          subtitle:
            "Find colleges and placement officers, import your campus hiring file, or search students.",
          placeholder: "Search colleges, placement officers, or students...",
          quickActions: [
            {
              label: "📥 Import campus hiring file",
              prompt: "How can I import our campus hiring file?",
            },
            {
              label: "🏛️ Colleges to contact in Mumbai",
              prompt: "Colleges to contact in Mumbai",
            },
            {
              label: "🎯 Search students by CGPA",
              prompt: "Search students by CGPA",
            },
          ],
        };
      case "recruiter":
        return {
          icon: "💼",
          title: "Welcome, Campus Recruiter!",
          subtitle: "Find placement officers at colleges, and draft outreach.",
          placeholder: "Find placement officers, draft outreach...",
          quickActions: [
            {
              label: "🏛️ Placement officers at engineering colleges",
              prompt:
                "Find placement officers at engineering colleges in Mumbai",
            },
          ],
        };
      case "student":
      default:
        return {
          icon: "🤖",
          title: "Welcome to your Recruiting Assistant!",
          subtitle:
            "Type or speak your details naturally, or tap “Add my resume” to extract your profile without filling forms.",
          placeholder: "Type your details (college, batch)...",
          quickActions: [
            {
              label: "📄 Add my resume",
              isResumeUpload: true,
            },
          ],
        };
    }
  }, [role]);

  function showToast(text: string) {
    setCrossDeviceToast(text);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = setTimeout(() => {
      setCrossDeviceToast(null);
    }, 4500);
  }

  // Save contact to user's list
  async function handleSaveContact(contactId: string) {
    if (!sessionToken || savingContactId) return;
    setSavingContactId(contactId);
    try {
      await withApiFallback((url) => {
        setCurrentBaseUrl(url);
        return saveContact(url, contactId, sessionToken);
      });
      setSavedContactIds((prev) => ({ ...prev, [contactId]: true }));
      showToast("Contact saved to your list");
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 429) {
        showToast("Rate limit reached. Please wait a moment.");
      } else {
        showToast(err?.message || "Failed to save contact");
      }
    } finally {
      setSavingContactId(null);
    }
  }

  // Remove contact from user's list
  async function handleRemoveContact(contactId: string) {
    if (!sessionToken || savingContactId) return;
    setSavingContactId(contactId);
    try {
      await withApiFallback((url) => {
        setCurrentBaseUrl(url);
        return removeSavedContact(url, contactId, sessionToken);
      });
      setSavedContactIds((prev) => {
        const next = { ...prev };
        delete next[contactId];
        return next;
      });
      showToast("Contact removed from your list");
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 429) {
        showToast("Rate limit reached. Please wait a moment.");
      } else {
        showToast(err?.message || "Failed to remove contact");
      }
    } finally {
      setSavingContactId(null);
    }
  }

  // 1. Authenticate & fetch user profile
  useEffect(() => {
    async function initAuth() {
      const {
        data: { session },
      } = await supabase.auth.getSession();
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

      // Load initial saved contacts
      withApiFallback((url) => {
        setCurrentBaseUrl(url);
        return listContacts(url, session.access_token, { saved_only: true });
      })
        .then((res) => {
          if (res?.items) {
            const savedMap: Record<string, boolean> = {};
            for (const c of res.items) {
              savedMap[c.id] = true;
            }
            setSavedContactIds((prev) => ({ ...prev, ...savedMap }));
          }
        })
        .catch(() => {});
    }
    initAuth();
  }, [router, supabase]);

  // 2. Supabase Realtime Subscription for cross-device sync
  useEffect(() => {
    if (!userId) return;

    // Messages sync with bidirectional deduplication
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
            const isUser = newEvent.source === "user_message";
            const eventText = (newEvent.payload?.message || "").trim();

            setMessages((prev) => {
              // 1. If this exact DB event UUID is already in the list, do nothing
              if (prev.some((m) => m.id === newEvent.id)) return prev;

              // 2. If it's a user message, check if we have a matching local optimistic message
              if (isUser) {
                const optUserIdx = prev.findIndex(
                  (m) =>
                    m.sender === "user" &&
                    (m.id.startsWith("user-") || m.text.trim() === eventText)
                );
                if (optUserIdx !== -1) {
                  const updated = [...prev];
                  updated[optUserIdx] = {
                    ...updated[optUserIdx],
                    id: newEvent.id,
                    timestamp: newEvent.created_at,
                  };
                  return updated;
                }
              }

              // 3. If it's an agent message, check if we already have it rendered from HTTP
              if (!isUser) {
                const agentIdx = prev.findIndex(
                  (m) =>
                    m.sender === "agent" &&
                    (m.id.startsWith("agent-") || m.text.trim() === eventText)
                );
                if (agentIdx !== -1) {
                  const updated = [...prev];
                  updated[agentIdx] = {
                    ...updated[agentIdx],
                    id: newEvent.id,
                    timestamp: newEvent.created_at,
                  };
                  return updated;
                }
              }

              // 4. Otherwise, this event was sent from another device (e.g. laptop) -> append it
              return [
                ...prev,
                {
                  id: newEvent.id,
                  sender: isUser ? "user" : "agent",
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

    // Saved contacts sync -> "Updated from your laptop"
    const savedContactsChannel = supabase
      .channel(`mobile_saved_contacts_${userId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "user_saved_contacts",
          filter: `profile_id=eq.${userId}`,
        },
        (payload) => {
          if (payload.eventType === "INSERT") {
            showToast("Saved contacts updated from your laptop");
            const cid = (payload.new as any)?.contact_id;
            if (cid) {
              setSavedContactIds((prev) => ({ ...prev, [cid]: true }));
            }
          } else if (payload.eventType === "DELETE") {
            showToast("Contact removed from your list from your laptop");
            const cid = (payload.old as any)?.contact_id;
            if (cid) {
              setSavedContactIds((prev) => {
                const next = { ...prev };
                delete next[cid];
                return next;
              });
            }
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(chatChannel);
      supabase.removeChannel(scoreChannel);
      supabase.removeChannel(profileChannel);
      supabase.removeChannel(savedContactsChannel);
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
    if (!text || isSendingRef.current || isSending || !sessionToken) return;
    isSendingRef.current = true;
    setIsSending(true);

    if (!overrideText) {
      setInputText("");
    }

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

    // Ensure view tracks user message without scroll conflicts
    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated: true });
    }, 50);

    try {
      const response = await withApiFallback((url) => {
        setCurrentBaseUrl(url);
        return chat(url, text, sessionToken);
      });

      // Extract confirmation cards from response.cards or step outputs
      const responseCards: ConfirmationCard[] = [...(response.cards || [])];
      if (response.steps) {
        for (const step of response.steps) {
          if (step.output && (step.output as any).card) {
            const cardObj = (step.output as any).card;
            if (
              !responseCards.some(
                (c) => c.title === cardObj.title && c.type === cardObj.type
              )
            ) {
              responseCards.push(cardObj);
            }
          }
        }
      }

      const agentId = `agent-${Date.now()}`;
      setMessages((prev) => {
        // Check if Realtime already received this reply while HTTP completed
        const existingAgentIdx = prev.findIndex(
          (m) =>
            m.sender === "agent" &&
            m.text.trim() === response.reply.trim() &&
            !m.steps &&
            !m.cards
        );

        if (existingAgentIdx !== -1) {
          const updated = [...prev];
          updated[existingAgentIdx] = {
            ...updated[existingAgentIdx],
            steps: response.steps,
            records: response.records_created,
            contacts: response.contacts,
            cards: responseCards.length > 0 ? responseCards : undefined,
          };
          return updated;
        }

        return [
          ...prev,
          {
            id: agentId,
            sender: "agent",
            text: response.reply,
            steps: response.steps,
            records: response.records_created,
            contacts: response.contacts,
            cards: responseCards.length > 0 ? responseCards : undefined,
            timestamp: new Date().toISOString(),
          },
        ];
      });

      if (isNearBottomRef.current) {
        setTimeout(() => {
          flatListRef.current?.scrollToEnd({ animated: true });
        }, 100);
      }
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
      isSendingRef.current = false;
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

      const res = await withApiFallback((url) => {
        setCurrentBaseUrl(url);
        return transcribeAudio(url, audioFile, "voice_note.m4a", sessionToken!);
      });

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

      const summary = await withApiFallback((url) => {
        setCurrentBaseUrl(url);
        return uploadResume(url, filePayload, asset.name, sessionToken);
      });

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
    await AsyncStorage.removeItem("demo_session");
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
    <SafeAreaView style={styles.safeArea} edges={["top", "left", "right"]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 10 : 0}
        style={[
          styles.container,
          { maxWidth: 680, width: "100%", alignSelf: "center" },
        ]}
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

        {/* Responsive Header */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Text
              numberOfLines={1}
              ellipsizeMode="tail"
              style={styles.headerTitle}
            >
              Recruiting Assistant
            </Text>
            <Text
              numberOfLines={1}
              ellipsizeMode="tail"
              style={styles.headerSubtitle}
            >
              {displayName} •{" "}
              <Text style={styles.roleText}>{role?.replace("_", " ")}</Text>
            </Text>
          </View>
          <View style={styles.headerRight}>
            <TouchableOpacity
              onPress={() => router.push("/my-list")}
              style={styles.myListHeaderBtn}
              accessibilityLabel="My saved list"
            >
              <Text style={styles.myListHeaderText}>🔖 List</Text>
            </TouchableOpacity>
            {role === "student" && (
              <TouchableOpacity
                onPress={() => router.push("/(tabs)/home")}
                style={styles.dashboardHeaderBtn}
                accessibilityLabel="Student dashboard"
              >
                <Text style={styles.dashboardHeaderText}>Dashboard</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity
              onPress={() => setShowServerModal(true)}
              style={styles.serverSettingsHeaderBtn}
              accessibilityLabel="Server connection settings"
            >
              <Text style={styles.serverSettingsHeaderText}>⚙️</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={handleSignOut}
              style={styles.signOutBtn}
              accessibilityLabel="Sign out"
            >
              <Text style={styles.signOutText}>Exit</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Message List */}
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messageList}
          onScroll={(e) => {
            const { layoutMeasurement, contentOffset, contentSize } =
              e.nativeEvent;
            const paddingToBottom = 120;
            isNearBottomRef.current =
              layoutMeasurement.height + contentOffset.y >=
              contentSize.height - paddingToBottom;
          }}
          scrollEventThrottle={32}
          onContentSizeChange={() => {
            if (isNearBottomRef.current) {
              flatListRef.current?.scrollToEnd({ animated: false });
            }
          }}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>{roleConfig.icon}</Text>
              <Text style={styles.emptyTitle}>{roleConfig.title}</Text>
              <Text style={styles.emptySubtitle}>{roleConfig.subtitle}</Text>
              <View style={styles.emptyActions}>
                {roleConfig.quickActions.map((qa, idx) => (
                  <TouchableOpacity
                    key={idx}
                    style={styles.emptyBtn}
                    onPress={() => {
                      if (qa.isResumeUpload) {
                        handleOpenResumePicker();
                      } else if (qa.prompt) {
                        setInputText(qa.prompt);
                      }
                    }}
                  >
                    <Text style={styles.emptyBtnText}>{qa.label}</Text>
                  </TouchableOpacity>
                ))}
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
            const hasRichCards =
              (item.contacts && item.contacts.length > 0) ||
              (item.cards && item.cards.length > 0) ||
              Boolean(summary);

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
                    isUser
                      ? styles.bubbleUser
                      : hasRichCards
                        ? styles.bubbleAgentFull
                        : styles.bubbleAgent,
                  ]}
                >
                  <Text
                    style={
                      isUser ? styles.bubbleTextUser : styles.bubbleTextAgent
                    }
                  >
                    {item.text}
                  </Text>

                  {item.text.includes("Error connecting to agent") && (
                    <TouchableOpacity
                      style={styles.retryConfigBtn}
                      onPress={() => setShowServerModal(true)}
                    >
                      <Text style={styles.retryConfigBtnText}>
                        ⚙️ Configure Server URL & Retry
                      </Text>
                    </TouchableOpacity>
                  )}

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

                  {/* Contact Cards */}
                  {item.contacts && item.contacts.length > 0 && (
                    <View style={styles.contactsContainer}>
                      {item.contacts
                        .filter((contact: ContactCard) => {
                          // Student record cards must render only for company and recruiter roles
                          if (
                            contact.role_type === "student" ||
                            contact.title?.toLowerCase().includes("student") ||
                            contact.title?.toLowerCase().includes("candidate")
                          ) {
                            return role === "company" || role === "recruiter";
                          }
                          return true;
                        })
                        .map((contact: ContactCard) => (
                          <MobileContactCard
                            key={contact.id}
                            contact={contact}
                            isSaved={
                              !!savedContactIds[contact.id] || !!contact.saved
                            }
                            isBusy={savingContactId === contact.id}
                            onSave={handleSaveContact}
                            onRemove={handleRemoveContact}
                            onDraft={(c: ContactCard) => setDraftingContact(c)}
                          />
                        ))}

                      {/* Short Privacy Note on Results */}
                      <View style={styles.privacyNoteBox}>
                        <Text style={styles.privacyNoteText}>
                          🛡 Public professional contact info only. Source and
                          date shown for every record. You can remove any saved
                          contact from My list at any time.
                        </Text>
                      </View>
                    </View>
                  )}

                  {/* Day 5 Action Confirmation Cards */}
                  {item.cards && item.cards.length > 0 && (
                    <View style={{ marginTop: 8 }}>
                      {item.cards.map(
                        (card: ConfirmationCard, cardIdx: number) => (
                          <MobileChatConfirmationCard
                            key={`${item.id}-card-${cardIdx}`}
                            card={card}
                            token={sessionToken || ""}
                            baseUrl={currentBaseUrl || API_BASE_URL}
                            onSuccess={(sc, msg) => {
                              if (msg) showToast(msg);
                            }}
                            onOpenUpload={handleOpenResumePicker}
                          />
                        )
                      )}
                    </View>
                  )}

                  {/* Agent Activity Expander */}
                  {hasStepsOrRecords &&
                    (() => {
                      const searchSummaryStep = item.steps?.find(
                        (s: AgentStep) =>
                          s.type === "search_summary" || s.summary
                      );
                      const summaryLine =
                        searchSummaryStep?.summary ||
                        (searchSummaryStep?.output as any)?.summary ||
                        (item.records?.length
                          ? `${item.records.length} record(s) synced • ${item.steps?.length || 0} step(s)`
                          : `${item.steps?.length || 0} agent step(s) completed`);

                      return (
                        <View style={styles.stepsContainer}>
                          <TouchableOpacity
                            onPress={() =>
                              setExpandedId(isExpanded ? null : item.id)
                            }
                            style={styles.stepsToggleBtn}
                          >
                            <Text style={styles.stepsToggle}>
                              {isExpanded ? "▾ " : "▸ "}Agent activity —{" "}
                              {summaryLine}
                            </Text>
                          </TouchableOpacity>

                          {isExpanded && (
                            <View style={styles.stepsDetails}>
                              {item.records?.map(
                                (rec: RecordRef, i: number) => (
                                  <Text key={i} style={styles.recText}>
                                    ✓ {rec.op.toUpperCase()}: {rec.table} (
                                    {rec.id})
                                  </Text>
                                )
                              )}
                              {item.steps?.map(
                                (step: AgentStep, idx: number) => (
                                  <View key={idx} style={styles.stepItem}>
                                    <Text style={styles.stepItemHeader}>
                                      [{step.type}] {step.tool || ""}
                                    </Text>
                                    {step.summary && (
                                      <Text style={styles.stepItemSummary}>
                                        {step.summary}
                                      </Text>
                                    )}
                                  </View>
                                )
                              )}
                            </View>
                          )}
                        </View>
                      );
                    })()}
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
        <View
          style={[
            styles.composer,
            {
              paddingHorizontal: isSmallWidth ? 8 : 12,
              paddingBottom: Math.max(insets.bottom, 8),
              gap: isSmallWidth ? 6 : 8,
            },
          ]}
        >
          {/* Add My Resume Button - Students only */}
          {role === "student" && (
            <TouchableOpacity
              style={[
                styles.resumeActionBtn,
                isSmallWidth && styles.actionBtnSmall,
              ]}
              onPress={handleOpenResumePicker}
              disabled={isSending || isTranscribing || isUploadingResume}
            >
              <Text style={styles.resumeActionIcon}>📎</Text>
            </TouchableOpacity>
          )}

          {/* Voice Mic Button */}
          <TouchableOpacity
            style={[
              styles.voiceBtn,
              isSmallWidth && styles.actionBtnSmall,
              isRecording && styles.voiceBtnRecording,
            ]}
            onPress={toggleVoiceRecording}
            disabled={isSending || isTranscribing || isUploadingResume}
          >
            <Text style={styles.voiceBtnText}>{isRecording ? "⏹" : "🎤"}</Text>
          </TouchableOpacity>

          <TextInput
            style={styles.composerInput}
            value={inputText}
            onChangeText={setInputText}
            placeholder={roleConfig.placeholder}
            placeholderTextColor="#94a3b8"
            returnKeyType="send"
            onSubmitEditing={() => {
              if (!isSendingRef.current && inputText.trim()) {
                handleSend();
              }
            }}
            blurOnSubmit={false}
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
              isSmallWidth && styles.actionBtnSmall,
              (!inputText.trim() || isSending || isRecording) &&
                styles.sendBtnDisabled,
            ]}
            onPress={() => {
              if (!isSendingRef.current && inputText.trim()) {
                handleSend();
              }
            }}
            disabled={!inputText.trim() || isSending || isRecording}
          >
            <Text style={styles.sendBtnText}>&rarr;</Text>
          </TouchableOpacity>
        </View>

        {/* Consent Modal Sheet - Students only */}
        {role === "student" && (
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
                  <Text style={styles.modalInfoText}>
                    • Formats: PDF or DOCX
                  </Text>
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
        )}
        {/* Backend Server Configuration Modal */}
        <Modal
          visible={showServerModal}
          animationType="fade"
          transparent={true}
          onRequestClose={() => setShowServerModal(false)}
        >
          <View style={styles.serverModalOverlay}>
            <View style={styles.serverModalContent}>
              <ScrollView
                showsVerticalScrollIndicator={false}
                contentContainerStyle={{ paddingBottom: 10 }}
              >
                <View style={styles.serverModalHeader}>
                  <Text style={styles.serverModalTitle}>
                    ⚙️ Backend Connection
                  </Text>
                  <TouchableOpacity onPress={() => setShowServerModal(false)}>
                    <Text style={styles.serverModalClose}>✕</Text>
                  </TouchableOpacity>
                </View>

                <Text style={styles.serverModalDesc}>
                  Current active server:
                </Text>
                <View style={styles.activeUrlBadge}>
                  <Text style={styles.activeUrlBadgeText}>
                    {currentBaseUrl}
                  </Text>
                </View>

                <Text style={[styles.serverModalDesc, { marginTop: 12 }]}>
                  Quick presets:
                </Text>
                <View style={styles.presetButtonsRow}>
                  <TouchableOpacity
                    style={[
                      styles.presetBtn,
                      { backgroundColor: "#eff6ff", borderColor: "#60a5fa" },
                    ]}
                    onPress={() => {
                      const tunnelUrl =
                        "https://towards-interference-paths-mag.trycloudflare.com";
                      setCustomServerUrlInput(tunnelUrl);
                      handleTestServerConnection(tunnelUrl);
                    }}
                  >
                    <Text
                      style={[
                        styles.presetBtnText,
                        { color: "#1d4ed8", fontWeight: "700" },
                      ]}
                    >
                      ☁️ Cloudflare HTTPS Tunnel
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.presetBtn}
                    onPress={() => {
                      setCustomServerUrlInput("http://10.0.2.2:8001");
                      handleTestServerConnection("http://10.0.2.2:8001");
                    }}
                  >
                    <Text style={styles.presetBtnText}>
                      📱 Emulator (10.0.2.2)
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.presetBtn}
                    onPress={() => {
                      setCustomServerUrlInput("http://192.168.29.133:8001");
                      handleTestServerConnection("http://192.168.29.133:8001");
                    }}
                  >
                    <Text style={styles.presetBtnText}>
                      📶 Wi-Fi LAN (192.168.29.133)
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.presetBtn}
                    onPress={() => {
                      setCustomServerUrlInput("http://localhost:8001");
                      handleTestServerConnection("http://localhost:8001");
                    }}
                  >
                    <Text style={styles.presetBtnText}>
                      💻 Localhost (8001)
                    </Text>
                  </TouchableOpacity>
                </View>

                <Text style={[styles.serverModalDesc, { marginTop: 12 }]}>
                  Custom Server or Public Tunnel URL:
                </Text>
                <TextInput
                  style={styles.serverUrlInput}
                  value={customServerUrlInput}
                  onChangeText={setCustomServerUrlInput}
                  placeholder="http://192.168.29.133:8001 or https://...loca.lt"
                  autoCapitalize="none"
                  autoCorrect={false}
                />

                {serverTestStatus && (
                  <Text style={styles.serverTestStatusText}>
                    {serverTestStatus}
                  </Text>
                )}

                <View style={styles.serverModalActions}>
                  <TouchableOpacity
                    style={styles.testBtn}
                    onPress={() => handleTestServerConnection()}
                    disabled={serverTestLoading}
                  >
                    {serverTestLoading ? (
                      <ActivityIndicator size="small" color="#1e40af" />
                    ) : (
                      <Text style={styles.testBtnText}>Test Connection</Text>
                    )}
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={styles.saveServerBtn}
                    onPress={() => handleApplyServerUrl()}
                  >
                    <Text style={styles.saveServerBtnText}>Save & Apply</Text>
                  </TouchableOpacity>
                </View>
              </ScrollView>
            </View>
          </View>
        </Modal>

        {/* Outreach Draft Message Sheet Modal */}
        <DraftMessageSheet
          visible={!!draftingContact}
          onClose={() => setDraftingContact(null)}
          contact={draftingContact}
          token={sessionToken}
          showToast={showToast}
        />
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
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#ffffff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  headerLeft: {
    flex: 1,
    minWidth: 0,
    marginRight: 6,
  },
  headerRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    flexShrink: 0,
  },
  headerTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: "#0f172a",
  },
  headerSubtitle: {
    fontSize: 11,
    color: "#64748b",
    marginTop: 1,
  },
  roleText: {
    color: "#4f46e5",
    fontWeight: "600",
    textTransform: "capitalize",
  },
  dashboardHeaderBtn: {
    paddingHorizontal: 7,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    backgroundColor: "#ffffff",
  },
  dashboardHeaderText: {
    fontSize: 11,
    color: "#4f46e5",
    fontWeight: "600",
  },
  myListHeaderBtn: {
    paddingHorizontal: 7,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#c7d2fe",
    backgroundColor: "#eef2ff",
  },
  myListHeaderText: {
    fontSize: 11,
    color: "#4338ca",
    fontWeight: "700",
  },
  signOutBtn: {
    paddingHorizontal: 7,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: "#f1f5f9",
  },
  signOutText: {
    fontSize: 11,
    color: "#475569",
    fontWeight: "600",
  },
  messageList: {
    paddingHorizontal: 10,
    paddingVertical: 12,
    paddingBottom: 20,
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
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
  },
  emptyBtn: {
    backgroundColor: "#eef2ff",
    borderWidth: 1,
    borderColor: "#c7d2fe",
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 7,
    maxWidth: "100%",
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
    maxWidth: "88%",
    paddingHorizontal: 12,
    paddingVertical: 9,
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
  bubbleAgentFull: {
    backgroundColor: "#ffffff",
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    maxWidth: "98%",
    width: "98%",
    paddingHorizontal: 8,
    paddingVertical: 8,
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
    flexWrap: "wrap",
    gap: 8,
    marginTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#e0e7ff",
    paddingTop: 8,
  },
  looksRightBtn: {
    flex: 1,
    minWidth: 90,
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
    minWidth: 90,
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
  contactsContainer: {
    marginTop: 8,
  },
  privacyNoteBox: {
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 8,
    padding: 8,
    marginTop: 6,
  },
  privacyNoteText: {
    fontSize: 10,
    color: "#64748b",
    lineHeight: 14,
  },
  stepsContainer: {
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
    paddingTop: 6,
  },
  stepsToggleBtn: {
    paddingVertical: 2,
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
    marginBottom: 2,
  },
  stepItem: {
    borderTopWidth: 1,
    borderTopColor: "#e2e8f0",
    paddingTop: 4,
    marginTop: 4,
  },
  stepItemHeader: {
    fontSize: 10,
    fontWeight: "600",
    color: "#475569",
  },
  stepItemSummary: {
    fontSize: 10,
    color: "#334155",
    marginTop: 2,
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
  serverSettingsHeaderBtn: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    backgroundColor: "#f1f5f9",
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#cbd5e1",
  },
  serverSettingsHeaderText: {
    fontSize: 14,
  },
  retryConfigBtn: {
    marginTop: 8,
    alignSelf: "flex-start",
    backgroundColor: "#eff6ff",
    borderWidth: 1,
    borderColor: "#3b82f6",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  retryConfigBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#1d4ed8",
  },
  actionBtnSmall: {
    width: 36,
    height: 36,
  },
  serverModalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
  },
  serverModalContent: {
    width: "100%",
    maxWidth: 480,
    maxHeight: "88%",
    backgroundColor: "#ffffff",
    borderRadius: 12,
    padding: 20,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 10,
    elevation: 6,
  },
  serverModalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  serverModalTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: "#0f172a",
  },
  serverModalClose: {
    fontSize: 18,
    color: "#64748b",
    padding: 4,
  },
  serverModalDesc: {
    fontSize: 13,
    color: "#475569",
    marginBottom: 6,
  },
  activeUrlBadge: {
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    padding: 8,
    borderRadius: 6,
  },
  activeUrlBadgeText: {
    fontFamily: Platform.OS === "ios" ? "Courier" : "monospace",
    fontSize: 13,
    color: "#0284c7",
    fontWeight: "600",
  },
  presetButtonsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginBottom: 10,
  },
  presetBtn: {
    backgroundColor: "#f1f5f9",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  presetBtnText: {
    fontSize: 12,
    color: "#334155",
    fontWeight: "500",
  },
  serverUrlInput: {
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
    color: "#0f172a",
    backgroundColor: "#fff",
    marginBottom: 10,
  },
  serverTestStatusText: {
    fontSize: 13,
    marginBottom: 10,
    color: "#0f172a",
  },
  serverModalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
    marginTop: 6,
  },
  testBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#93c5fd",
    backgroundColor: "#eff6ff",
    justifyContent: "center",
  },
  testBtnText: {
    color: "#1e40af",
    fontSize: 13,
    fontWeight: "600",
  },
  saveServerBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: "#2563eb",
    justifyContent: "center",
  },
  saveServerBtnText: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "600",
  },
});
