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
} from "react-native";
import { useRouter } from "expo-router";
import { getMobileSupabaseClient, API_BASE_URL } from "../lib/supabase";
import { chat, AgentStep, RecordRef, RawEvent } from "@recruiting/shared";

interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  steps?: AgentStep[];
  records?: RecordRef[];
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

  const flatListRef = useRef<FlatList>(null);

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

    const channel = supabase
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

    return () => {
      supabase.removeChannel(channel);
    };
  }, [userId, supabase]);

  async function handleSend() {
    if (!inputText.trim() || isSending || !sessionToken) return;
    const text = inputText.trim();
    setInputText("");
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

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.container}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>Recruiting Assistant</Text>
            <Text style={styles.headerSubtitle}>
              {displayName} •{" "}
              <Text style={styles.roleText}>{role?.replace("_", " ")}</Text>
            </Text>
          </View>
          <TouchableOpacity onPress={handleSignOut} style={styles.signOutBtn}>
            <Text style={styles.signOutText}>Sign Out</Text>
          </TouchableOpacity>
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
          renderItem={({ item }) => {
            const isUser = item.sender === "user";
            const isExpanded = expandedId === item.id;
            const hasStepsOrRecords =
              (item.steps && item.steps.length > 0) ||
              (item.records && item.records.length > 0);

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

        {isSending && (
          <View style={styles.typingIndicator}>
            <ActivityIndicator size="small" color="#4f46e5" />
            <Text style={styles.typingText}>
              Agent is updating structured records...
            </Text>
          </View>
        )}

        {/* Composer */}
        <View style={styles.composer}>
          {/* Disabled Voice Affordance */}
          <TouchableOpacity disabled style={styles.voiceBtn}>
            <Text style={styles.voiceBtnText}>🎤</Text>
            <View style={styles.day2Badge}>
              <Text style={styles.day2Text}>Day 2</Text>
            </View>
          </TouchableOpacity>

          <TextInput
            style={styles.composerInput}
            value={inputText}
            onChangeText={setInputText}
            placeholder="Type your details (college, batch, company)..."
            placeholderTextColor="#94a3b8"
            editable={!isSending}
          />

          <TouchableOpacity
            style={[
              styles.sendBtn,
              (!inputText.trim() || isSending) && styles.sendBtnDisabled,
            ]}
            onPress={handleSend}
            disabled={!inputText.trim() || isSending}
          >
            <Text style={styles.sendBtnText}>&rarr;</Text>
          </TouchableOpacity>
        </View>
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
    maxWidth: "82%",
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
  voiceBtn: {
    width: 42,
    height: 42,
    borderRadius: 12,
    backgroundColor: "#f1f5f9",
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
  },
  voiceBtnText: {
    fontSize: 18,
    opacity: 0.4,
  },
  day2Badge: {
    position: "absolute",
    top: -4,
    right: -4,
    backgroundColor: "#0f172a",
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: 6,
  },
  day2Text: {
    color: "#ffffff",
    fontSize: 8,
    fontWeight: "700",
  },
  composerInput: {
    flex: 1,
    backgroundColor: "#f8fafc",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: "#0f172a",
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 12,
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
});
