"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import { chat, AgentStep, RecordRef, RawEvent } from "@recruiting/shared";
import {
  Send,
  Mic,
  Bot,
  User,
  LogOut,
  ChevronDown,
  ChevronUp,
  Database,
  CheckCircle2,
  Loader2,
  Sparkles,
} from "lucide-react";

interface ChatItem {
  id: string;
  sender: "user" | "agent";
  text: string;
  steps?: AgentStep[];
  records?: RecordRef[];
  timestamp: string;
}

export default function ChatPage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>(
    {}
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 1. Check Session & Load Profile
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

      // Load initial message history from raw_events
      loadInitialHistory(session.user.id);
    });
  }, [router, supabase]);

  async function loadInitialHistory(actorId: string) {
    const { data: events, error } = await supabase
      .from("raw_events")
      .select("*")
      .eq("actor_id", actorId)
      .in("source", ["user_message", "agent_message"])
      .order("created_at", { ascending: true })
      .limit(100);

    if (events && !error) {
      const items: ChatItem[] = events.map((ev: RawEvent) => ({
        id: ev.id,
        sender: ev.source === "user_message" ? "user" : "agent",
        text: ev.payload?.message || "",
        timestamp: ev.created_at,
      }));
      setMessages(items);
    }
  }

  // 2. Supabase Realtime Subscription for raw_events
  useEffect(() => {
    if (!userId) return;

    const channel = supabase
      .channel(`raw_events_${userId}`)
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
              // Avoid duplicate if already locally appended
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

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  // 3. Send Message to Agent
  async function handleSend(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!inputText.trim() || isSending || !sessionToken) return;

    const text = inputText.trim();
    setInputText("");
    setIsSending(true);

    const tempUserId = `user-${Date.now()}`;
    // Optimistic UI append
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
          id: `error-${Date.now()}`,
          sender: "agent",
          text: `Error connecting to agent: ${err.message || "Please verify API service."}`,
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

  function toggleSteps(id: string) {
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  return (
    <div className="flex h-screen flex-col bg-slate-50">
      {/* Top Navigation */}
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900">
              Campus Recruiting Agent
            </h1>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">{displayName}</span>
              <span className="rounded-full bg-indigo-100 px-2 py-0.2 text-[10px] font-semibold text-indigo-700 capitalize">
                {role?.replace("_", " ")}
              </span>
            </div>
          </div>
        </div>

        <button
          onClick={handleSignOut}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign Out</span>
        </button>
      </header>

      {/* Chat Messages List */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 && (
            <div className="my-12 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                <Bot className="h-6 w-6" />
              </div>
              <h2 className="text-base font-semibold text-slate-800">
                Welcome to your Recruiting Assistant!
              </h2>
              <p className="mx-auto mt-1 max-w-sm text-xs text-slate-500">
                Type your details naturally (e.g. your college, batch, degree,
                or company). The agent automatically builds structured records
                on your behalf.
              </p>
            </div>
          )}

          {messages.map((item) => {
            const isUser = item.sender === "user";
            const isExpanded = !!expandedSteps[item.id];
            const hasStepsOrRecords =
              (item.steps && item.steps.length > 0) ||
              (item.records && item.records.length > 0);

            return (
              <div
                key={item.id}
                className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
              >
                {!isUser && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white">
                    <Bot className="h-4 w-4" />
                  </div>
                )}

                <div
                  className={`max-w-[85%] sm:max-w-xl rounded-2xl p-4 text-sm ${
                    isUser
                      ? "bg-indigo-600 text-white"
                      : "border border-slate-200 bg-white text-slate-800 shadow-sm"
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">
                    {item.text}
                  </p>

                  {/* Agent Steps / Tool Calls Inspection Accordion */}
                  {hasStepsOrRecords && (
                    <div className="mt-3 border-t border-slate-100 pt-2 text-xs">
                      <button
                        type="button"
                        onClick={() => toggleSteps(item.id)}
                        className="flex w-full items-center justify-between text-indigo-600 hover:text-indigo-700"
                      >
                        <span className="flex items-center gap-1 font-semibold">
                          <Database className="h-3.5 w-3.5" />
                          <span>
                            {item.records?.length
                              ? `${item.records.length} record(s) synced`
                              : `${item.steps?.length} agent step(s)`}
                          </span>
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </button>

                      {isExpanded && (
                        <div className="mt-2 space-y-2 rounded-lg bg-slate-50 p-2.5 font-mono text-[11px] text-slate-700">
                          {item.records?.map((rec, i) => (
                            <div
                              key={i}
                              className="flex items-center gap-1.5 text-emerald-600 font-sans"
                            >
                              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                              <span>
                                {rec.op.toUpperCase()}:{" "}
                                <strong className="font-semibold">
                                  {rec.table}
                                </strong>{" "}
                                ({rec.id})
                              </span>
                            </div>
                          ))}

                          {item.steps?.map((step, idx) => (
                            <div
                              key={idx}
                              className="border-t border-slate-200 pt-1.5"
                            >
                              <div className="font-semibold text-slate-600">
                                [{step.type}] {step.tool || ""}
                              </div>
                              {step.input && (
                                <pre className="mt-1 overflow-x-auto text-[10px] text-slate-600">
                                  {JSON.stringify(step.input, null, 2)}
                                </pre>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {isUser && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-300 text-slate-700">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            );
          })}

          {isSending && (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500 shadow-sm">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
                <span>Agent is updating structured records...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Composer */}
      <footer className="border-t border-slate-200 bg-white p-4">
        <form
          onSubmit={handleSend}
          className="mx-auto flex max-w-3xl items-center gap-2"
        >
          {/* Voice Input Affordance - Disabled with Day 2 Badge */}
          <div className="relative group">
            <button
              type="button"
              disabled
              title="Voice input is coming in Day 2"
              className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed"
            >
              <Mic className="h-5 w-5" />
            </button>
            <span className="absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900 px-1.5 py-0.5 text-[9px] font-semibold text-white opacity-0 group-hover:opacity-100 transition">
              Day 2 (Voice)
            </span>
          </div>

          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your details (e.g. I am Riya at St. Xavier's, batch 2027, BSc CS)..."
            disabled={isSending}
            className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={!inputText.trim() || isSending}
            className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
      </footer>
    </div>
  );
}
