"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import { getCurrentSession, logout } from "@/lib/auth";
import {
  chat,
  transcribeAudio,
  uploadResume,
  saveContact,
  removeSavedContact,
  listContacts,
  AgentStep,
  RecordRef,
  RawEvent,
  ResumeResponse,
  ContactCard,
  ConfirmationCard,
  ApiError,
} from "@recruiting/shared";
import { ContactCardItem } from "@/app/components/ContactCardItem";
import { DraftMessageModal } from "@/app/components/DraftMessageModal";
import { ChatConfirmationCard } from "@/app/components/ChatConfirmationCard";
import { SwitchDemoRoleButton } from "@/app/components/SwitchDemoRoleButton";
import {
  Send,
  Mic,
  Square,
  Bot,
  User,
  LogOut,
  ChevronDown,
  ChevronUp,
  Database,
  CheckCircle2,
  Loader2,
  Sparkles,
  Paperclip,
  FileText,
  AlertCircle,
  Smartphone,
  X,
  ArrowRight,
  RefreshCw,
  Bookmark,
  ExternalLink,
  Mail,
  ShieldCheck,
} from "lucide-react";

interface QuickActionItem {
  label: string;
  prompt?: string;
  isResumeUpload?: boolean;
}

interface RoleChatConfig {
  title: string;
  subtitle: string;
  placeholder: string;
  quickActions: QuickActionItem[];
}

interface ChatItem {
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

export default function ChatPage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState(false);
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [inputText, setInputText] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>(
    {}
  );

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  // Resume upload state
  const [isConsentOpen, setIsConsentOpen] = useState(false);
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);

  // Cross-device sync toast state
  const [crossDeviceToast, setCrossDeviceToast] = useState<string | null>(null);

  // Saved contacts state
  const [savedContactIds, setSavedContactIds] = useState<
    Record<string, boolean>
  >({});
  const [savingContactId, setSavingContactId] = useState<string | null>(null);

  // Outreach draft modal state
  const [draftingContact, setDraftingContact] = useState<ContactCard | null>(
    null
  );

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const roleConfig: RoleChatConfig = useMemo(() => {
    switch (role) {
      case "placement_officer":
        return {
          title: "Welcome, Placement Officer!",
          subtitle:
            "Import your student list, search students by batch or status, or find companies to invite for campus hiring.",
          placeholder: "Search students by batch, find hiring companies...",
          quickActions: [
            {
              label: "Import student list (CSV)",
              prompt: "How can I import our student list via CSV?",
            },
            {
              label: "Companies to contact for BE Computer Science/IT/AI",
              prompt: "Companies to contact for BE Computer Science/IT/AI",
            },
          ],
        };
      case "company":
        return {
          title: "Welcome, Hiring Partner!",
          subtitle:
            "Find colleges and placement officers, import your campus hiring file, or search students.",
          placeholder: "Search colleges, placement officers, or students...",
          quickActions: [
            {
              label: "Import campus hiring file",
              prompt: "How can I import our campus hiring file?",
            },
            {
              label: "Colleges to contact in Mumbai",
              prompt: "Colleges to contact in Mumbai",
            },
            {
              label: "Search students by CGPA",
              prompt: "Search students by CGPA",
            },
          ],
        };
      case "recruiter":
        return {
          title: "Welcome, Campus Recruiter!",
          subtitle: "Find placement officers at colleges, and draft outreach.",
          placeholder: "Find placement officers, draft outreach...",
          quickActions: [
            {
              label: "Placement officers at engineering colleges",
              prompt:
                "Find placement officers at engineering colleges in Mumbai",
            },
          ],
        };
      case "student":
      default:
        return {
          title: "Welcome to your Recruiting Assistant!",
          subtitle:
            "Type or speak your details naturally, or tap “Add my resume” below to automatically extract your profile.",
          placeholder:
            "Type your details (e.g. I am Riya at St. Xavier's, batch 2027, BSc CS)...",
          quickActions: [
            {
              label: "Add my resume",
              isResumeUpload: true,
            },
          ],
        };
    }
  }, [role]);

  // Show temporary toast
  function showToast(message: string) {
    setCrossDeviceToast(message);
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
      await saveContact(API_BASE_URL, contactId, sessionToken);
      setSavedContactIds((prev) => ({ ...prev, [contactId]: true }));
      showToast("Contact saved to your list");
    } catch (err: any) {
      console.error("Failed to save contact:", err);
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
      await removeSavedContact(API_BASE_URL, contactId, sessionToken);
      setSavedContactIds((prev) => {
        const next = { ...prev };
        delete next[contactId];
        return next;
      });
      showToast("Contact removed from your list");
    } catch (err: any) {
      console.error("Failed to remove contact:", err);
      if (err instanceof ApiError && err.status === 429) {
        showToast("Rate limit reached. Please wait a moment.");
      } else {
        showToast(err?.message || "Failed to remove contact");
      }
    } finally {
      setSavingContactId(null);
    }
  }

  // 1. Check Session & Load Profile
  useEffect(() => {
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

    getCurrentSession().then(async (userSession) => {
      if (!userSession) {
        router.replace("/login");
        return;
      }
      if (!userSession.user.role) {
        router.replace("/onboarding");
        return;
      }
      setSessionToken(userSession.token);
      setUserId(userSession.user.id);
      setRole(userSession.user.role);
      setDisplayName(userSession.user.displayName);

      setIsDemo(Boolean(userSession.user.isDemo));

      // Load initial message history
      loadInitialHistory(userSession.user.id);

      // Load initial saved contacts
      listContacts(API_BASE_URL, userSession.token, { saved_only: true })
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
    });
  }, [router, supabase]);

  // 2. Supabase Realtime Subscription for raw_events, score_events, and profile tables
  useEffect(() => {
    if (!userId) return;

    const chanId = Math.random().toString(36).slice(2, 7);

    // A. Chat messages sync
    const chatChannel = supabase
      .channel(`raw_events_${userId}_${chanId}`)
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

    // B. Realtime updates of score and profile with the "updated from your phone" toast
    const scoreChannel = supabase
      .channel(`score_events_${userId}_${chanId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "score_events",
          filter: `profile_id=eq.${userId}`,
        },
        (payload) => {
          const newScore = (payload.new as any)?.score;
          showToast(
            newScore !== undefined
              ? `Score updated to ${newScore} from your phone`
              : "Score & profile updated from your phone"
          );
        }
      )
      .subscribe();

    const profileChannel = supabase
      .channel(`profile_changes_${userId}_${chanId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "education",
          filter: `profile_id=eq.${userId}`,
        },
        () => showToast("Profile updated from your phone")
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "internships",
          filter: `profile_id=eq.${userId}`,
        },
        () => showToast("Profile updated from your phone")
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "skills",
          filter: `profile_id=eq.${userId}`,
        },
        () => showToast("Profile updated from your phone")
      )
      .subscribe();

    // D. Realtime updates of user saved contacts with the "updated from your phone" toast
    const savedContactsChannel = supabase
      .channel(`saved_contacts_sync_${userId}_${chanId}`)
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
            showToast("Saved contacts updated from your phone");
            const cid = (payload.new as any)?.contact_id;
            if (cid) {
              setSavedContactIds((prev) => ({ ...prev, [cid]: true }));
            }
          } else if (payload.eventType === "DELETE") {
            showToast("Contact removed from your list from your phone");
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

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending, isTranscribing, isUploadingResume]);

  // Clean up recording timer on unmount
  useEffect(() => {
    return () => {
      if (recordIntervalRef.current) clearInterval(recordIntervalRef.current);
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state === "recording"
      ) {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  // 3. Send Message to Agent
  async function handleSend(e?: React.FormEvent, overrideText?: string) {
    if (e) e.preventDefault();
    const text = (overrideText ?? inputText).trim();
    if (!text || isSending || !sessionToken) return;

    if (!overrideText) {
      setInputText("");
    }
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
      setMessages((prev) => [
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

  // 4. Voice Recording & Transcription
  async function startRecording() {
    setVoiceError(null);
    if (!sessionToken) {
      setVoiceError("Please wait for your session to load.");
      return;
    }

    if (
      typeof window === "undefined" ||
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia
    ) {
      setVoiceError("Voice recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      let mimeType = "audio/webm";
      if (!MediaRecorder.isTypeSupported("audio/webm")) {
        if (MediaRecorder.isTypeSupported("audio/mp4")) {
          mimeType = "audio/mp4";
        } else if (MediaRecorder.isTypeSupported("audio/ogg")) {
          mimeType = "audio/ogg";
        } else {
          mimeType = "";
        }
      }

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        // Stop all audio tracks
        stream.getTracks().forEach((track) => track.stop());

        if (recordIntervalRef.current) {
          clearInterval(recordIntervalRef.current);
          recordIntervalRef.current = null;
        }

        const audioBlob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });

        if (audioBlob.size < 500) {
          setVoiceError(
            "Recording was too short or silent. Please try speaking again."
          );
          setIsTranscribing(false);
          setIsRecording(false);
          return;
        }

        setIsTranscribing(true);
        try {
          const extension = recorder.mimeType.includes("mp4") ? "mp4" : "webm";
          const res = await transcribeAudio(
            API_BASE_URL,
            audioBlob,
            `voice_input.${extension}`,
            sessionToken
          );

          if (res.text && res.text.trim()) {
            // Feed transcript directly into chat flow
            await handleSend(undefined, res.text.trim());
          } else {
            setVoiceError("Could not recognize any speech. Please try again.");
          }
        } catch (err: any) {
          setVoiceError(
            err.message ||
              "Voice transcription failed. Please try again or type instead."
          );
        } finally {
          setIsTranscribing(false);
          setIsRecording(false);
        }
      };

      recorder.start(250);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordingSeconds(0);

      recordIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      if (
        err.name === "NotAllowedError" ||
        err.name === "PermissionDeniedError" ||
        err.message?.includes("Permission denied")
      ) {
        setVoiceError(
          "Microphone permission was denied. Please allow microphone access in your browser."
        );
      } else {
        setVoiceError(
          `Failed to access microphone: ${err.message || "Unknown error"}`
        );
      }
      setIsRecording(false);
    }
  }

  function stopRecording() {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      mediaRecorderRef.current.stop();
    }
  }

  function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  // 5. Resume Upload with Consent Sheet & Parsed Card
  function handleOpenResumePicker() {
    setResumeError(null);
    setIsConsentOpen(true);
  }

  function handleConsentConfirm() {
    setIsConsentOpen(false);
    // Open hidden file picker
    fileInputRef.current?.click();
  }

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset input value so same file can be selected again if needed
    e.target.value = "";
    if (!file || !sessionToken) return;

    setResumeError(null);

    // Validate size (max 5MB)
    const MAX_SIZE = 5 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      setResumeError(
        `File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum allowed size is 5 MB.`
      );
      return;
    }

    // Validate extension / MIME
    const fname = file.name.toLowerCase();
    const isPdfOrDocx =
      fname.endsWith(".pdf") ||
      fname.endsWith(".docx") ||
      file.type === "application/pdf" ||
      file.type ===
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

    if (!isPdfOrDocx) {
      setResumeError("Only PDF and DOCX files are supported.");
      return;
    }

    setIsUploadingResume(true);

    // Optimistic user note
    const userMsgId = `user-resume-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        sender: "user",
        text: `Uploaded resume: ${file.name}`,
        timestamp: new Date().toISOString(),
      },
    ]);

    try {
      const summary = await uploadResume(
        API_BASE_URL,
        file,
        file.name,
        sessionToken
      );

      const agentMsgId = `agent-resume-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: agentMsgId,
          sender: "agent",
          text: `I've analyzed your resume "${file.name}" and extracted your academic and work experience! Your readiness score is now ${summary.score.score}/100.`,
          records: summary.records_created,
          resumeSummary: summary,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err: any) {
      setResumeError(err.message || "Failed to upload and parse resume.");
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          sender: "agent",
          text: `Resume upload error: ${err.message || "Could not process file."}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsUploadingResume(false);
    }
  }

  function handleFixSomething(summary: ResumeResponse) {
    const missing = summary.missing_fields?.length
      ? summary.missing_fields.join(", ")
      : "details";
    setInputText(`I want to fix or add info for: ${missing}. Specifically: `);
  }

  async function handleSignOut() {
    await logout();
    router.replace("/login");
  }

  function toggleSteps(id: string) {
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  const formatTimer = (secs: number) => {
    const m = Math.floor(secs / 60)
      .toString()
      .padStart(2, "0");
    const s = (secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  return (
    <div className="flex h-screen flex-col bg-slate-50 relative">
      {/* Hidden File Input for Resume */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelected}
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
      />

      {/* Cross-Device Live Update Toast */}
      {crossDeviceToast && (
        <div className="absolute top-20 right-6 z-50 flex items-center gap-2.5 rounded-xl border border-indigo-200 bg-white px-4 py-3 text-xs font-medium text-slate-800 shadow-lg animate-in fade-in slide-in-from-top-4">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
            <Smartphone className="h-3.5 w-3.5" />
          </div>
          <div>
            <p className="font-semibold text-slate-900">{crossDeviceToast}</p>
            <p className="text-[10px] text-slate-400">Synced in realtime</p>
          </div>
          <button
            onClick={() => setCrossDeviceToast(null)}
            className="ml-2 text-slate-400 hover:text-slate-600"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

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

        <div className="flex items-center gap-3">
          <Link
            href="/my-list"
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 hover:text-indigo-600 shadow-2xs"
          >
            <Bookmark className="h-3.5 w-3.5 text-indigo-600" />
            <span>My list</span>
          </Link>

          {role === "student" && (
            <Link
              href="/home"
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 hover:text-indigo-600"
            >
              <span>Student Dashboard</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          )}

          {role === "placement_officer" && (
            <Link
              href="/officer/home"
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 hover:text-indigo-600"
            >
              <span>Officer Dashboard</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          )}

          {role === "company" && (
            <Link
              href="/company/home"
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 hover:text-indigo-600"
            >
              <span>Company Dashboard</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          )}

          {isDemo && <SwitchDemoRoleButton />}

          <button
            onClick={handleSignOut}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
          >
            <LogOut className="h-4 w-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Demo Session Notice */}
      {isDemo && (
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 text-xs text-amber-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span>
              <strong>Demo Mode:</strong> You are logged into an isolated demo
              session.
            </span>
          </div>
          <span className="text-[10px] text-amber-600 font-semibold uppercase tracking-wider">
            Sandboxed
          </span>
        </div>
      )}

      {/* Error Banners */}
      {(voiceError || resumeError) && (
        <div className="bg-red-50 border-b border-red-200 px-6 py-2.5 flex items-center justify-between text-xs text-red-700">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />
            <span>{voiceError || resumeError}</span>
          </div>
          <button
            onClick={() => {
              setVoiceError(null);
              setResumeError(null);
            }}
            className="text-red-500 hover:text-red-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Chat Messages List */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {messages.length === 0 && (
            <div className="my-12 text-center">
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                <Bot className="h-6 w-6" />
              </div>
              <h2 className="text-base font-semibold text-slate-800">
                {roleConfig.title}
              </h2>
              <p className="mx-auto mt-1 max-w-sm text-xs text-slate-500">
                {roleConfig.subtitle}
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {roleConfig.quickActions.map((qa, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      if (qa.isResumeUpload) {
                        handleOpenResumePicker();
                      } else if (qa.prompt) {
                        setInputText(qa.prompt);
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition"
                  >
                    {qa.isResumeUpload && <FileText className="h-3.5 w-3.5" />}
                    <span>{qa.label}</span>
                  </button>
                ))}
                <button
                  type="button"
                  onClick={toggleRecording}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                >
                  <Mic className="h-3.5 w-3.5 text-indigo-600" />
                  <span>Speak via Voice</span>
                </button>
              </div>
            </div>
          )}

          {messages.map((item) => {
            const isUser = item.sender === "user";
            const isExpanded = !!expandedSteps[item.id];
            const hasStepsOrRecords =
              (item.steps && item.steps.length > 0) ||
              (item.records && item.records.length > 0);
            const summary = item.resumeSummary;

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

                  {/* Parsed-Summary Card for Resumes */}
                  {summary && (
                    <div className="mt-3 rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50/70 to-blue-50/50 p-3.5 text-slate-800">
                      <div className="flex items-center justify-between border-b border-indigo-100 pb-2.5">
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white">
                            <FileText className="h-4 w-4" />
                          </div>
                          <div>
                            <span className="text-xs font-bold text-slate-900">
                              Resume Summary Card
                            </span>
                            <p className="text-[10px] text-slate-500">
                              {summary.records_created?.length || 0} record(s)
                              synced
                            </p>
                          </div>
                        </div>
                        <div className="flex items-baseline gap-1 rounded-full bg-indigo-600 px-2.5 py-0.5 text-white">
                          <span className="text-xs font-bold">
                            {summary.score.score}
                          </span>
                          <span className="text-[9px] opacity-80">/ 100</span>
                        </div>
                      </div>

                      {/* Extracted Breakdown Preview */}
                      <div className="my-2.5 space-y-1.5 text-xs">
                        <div className="text-[11px] font-semibold text-slate-600">
                          Top Factors:
                        </div>
                        {summary.score.breakdown?.slice(0, 3).map((item, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between text-[11px] text-slate-600"
                          >
                            <span className="truncate pr-2">
                              • {item.reason}
                            </span>
                            <span className="font-semibold text-emerald-600 shrink-0">
                              +{item.points}
                            </span>
                          </div>
                        ))}

                        {summary.missing_fields &&
                          summary.missing_fields.length > 0 && (
                            <div className="mt-2 rounded-lg bg-amber-50 p-2 text-[11px] text-amber-800 border border-amber-200/60">
                              <span className="font-semibold">
                                Missing fields to boost score:{" "}
                              </span>
                              {summary.missing_fields.join(", ")}
                            </div>
                          )}
                      </div>

                      {/* Action buttons: "Looks right" / "Fix something" */}
                      <div className="mt-3 flex items-center gap-2 pt-2 border-t border-indigo-100">
                        <Link
                          href="/home"
                          className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 transition"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          <span>Looks right</span>
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleFixSomething(summary)}
                          className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                        >
                          <RefreshCw className="h-3 w-3 text-slate-500" />
                          <span>Fix something</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Recruiter / Contact Cards */}
                  {item.contacts && item.contacts.length > 0 && (
                    <div className="mt-3 space-y-2.5">
                      {item.contacts
                        .filter((contact) => {
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
                        .map((contact) => (
                          <ContactCardItem
                            key={contact.id}
                            contact={contact}
                            isSaved={
                              !!savedContactIds[contact.id] || !!contact.saved
                            }
                            isBusy={savingContactId === contact.id}
                            onSave={handleSaveContact}
                            onRemove={handleRemoveContact}
                            onDraft={(c) => setDraftingContact(c)}
                          />
                        ))}

                      {/* Short Privacy Note on Results */}
                      <div className="mt-2 flex items-start gap-1.5 rounded-lg border border-slate-200/80 bg-slate-50/70 p-2.5 text-[11px] text-slate-600">
                        <ShieldCheck className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
                        <span>
                          Public professional contact info only. Source and date
                          shown for every record. You can remove any saved
                          contact from My list at any time.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Day 5 Action Confirmation Cards */}
                  {item.cards && item.cards.length > 0 && (
                    <div className="mt-3 space-y-2.5">
                      {item.cards.map((card, cardIdx) => (
                        <ChatConfirmationCard
                          key={`${item.id}-card-${cardIdx}`}
                          card={card}
                          token={sessionToken || ""}
                          baseUrl={API_BASE_URL}
                          onSuccess={(sc, msg) => {
                            if (msg) showToast(msg);
                          }}
                          onOpenUpload={() => setIsConsentOpen(true)}
                        />
                      ))}
                    </div>
                  )}

                  {/* Agent Activity / Step Log Expander */}
                  {hasStepsOrRecords &&
                    (() => {
                      const searchSummaryStep = item.steps?.find(
                        (s) => s.type === "search_summary" || s.summary
                      );
                      const summaryLine =
                        searchSummaryStep?.summary ||
                        (searchSummaryStep?.output as any)?.summary ||
                        (item.records?.length
                          ? `${item.records.length} record(s) synced • ${item.steps?.length || 0} step(s)`
                          : `${item.steps?.length || 0} agent step(s) completed`);

                      return (
                        <div className="mt-3 border-t border-slate-100 pt-2 text-xs">
                          <button
                            type="button"
                            onClick={() => toggleSteps(item.id)}
                            className="flex w-full items-center justify-between text-indigo-600 hover:text-indigo-700 font-medium py-1"
                          >
                            <span className="flex items-center gap-1.5 font-semibold text-slate-700">
                              <Database className="h-3.5 w-3.5 text-indigo-600" />
                              <span>Agent activity</span>
                              <span className="font-normal text-slate-500 text-[11px] truncate max-w-[280px] sm:max-w-md">
                                — {summaryLine}
                              </span>
                            </span>
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" />
                            ) : (
                              <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
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
                                  {step.summary && (
                                    <div className="mt-1 text-slate-700 font-sans text-xs">
                                      Summary: {step.summary}
                                    </div>
                                  )}
                                  {step.input && (
                                    <pre className="mt-1 overflow-x-auto text-[10px] text-slate-600">
                                      {JSON.stringify(step.input, null, 2)}
                                    </pre>
                                  )}
                                  {step.output &&
                                    step.type !== "search_summary" && (
                                      <pre className="mt-1 overflow-x-auto text-[10px] text-slate-500">
                                        {JSON.stringify(step.output, null, 2)}
                                      </pre>
                                    )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                </div>

                {isUser && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-300 text-slate-700">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            );
          })}

          {/* Active Loading States */}
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

          {isTranscribing && (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white">
                <Mic className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl border border-indigo-200 bg-indigo-50/50 px-4 py-3 text-xs text-indigo-700 shadow-sm">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
                <span>Transcribing your voice note...</span>
              </div>
            </div>
          )}

          {isUploadingResume && (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white">
                <FileText className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl border border-indigo-200 bg-indigo-50/50 px-4 py-3 text-xs text-indigo-700 shadow-sm">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
                <span>
                  Reading and extracting resume details without forms...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Recording Indicator Overlay Bar */}
      {isRecording && (
        <div className="border-t border-red-200 bg-red-50/90 px-6 py-2 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-600"></span>
            </span>
            <span className="text-xs font-semibold text-red-700">
              Recording audio: {formatTimer(recordingSeconds)}
            </span>
            <span className="text-[11px] text-red-500">
              Speak naturally (English, Hindi, Marathi)
            </span>
          </div>

          <button
            type="button"
            onClick={stopRecording}
            className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1 text-xs font-semibold text-white hover:bg-red-700 transition"
          >
            <Square className="h-3 w-3 fill-current" />
            <span>Finish & Transcribe</span>
          </button>
        </div>
      )}

      {/* Input Composer */}
      <footer className="border-t border-slate-200 bg-white p-4">
        <form
          onSubmit={(e) => handleSend(e)}
          className="mx-auto flex max-w-3xl items-center gap-2"
        >
          {/* Resume Upload Action Button ("Add my resume") - Students only */}
          {role === "student" && (
            <button
              type="button"
              onClick={handleOpenResumePicker}
              disabled={isSending || isTranscribing || isUploadingResume}
              title="Add my resume"
              className="flex h-11 items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs font-medium text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-600 transition disabled:opacity-50"
            >
              <Paperclip className="h-4 w-4" />
              <span className="hidden sm:inline">Add my resume</span>
            </button>
          )}

          {/* Voice Input Mic Button */}
          <button
            type="button"
            onClick={toggleRecording}
            disabled={isSending || isTranscribing || isUploadingResume}
            title={isRecording ? "Stop recording" : "Record voice message"}
            className={`flex h-11 w-11 items-center justify-center rounded-xl border transition ${
              isRecording
                ? "border-red-500 bg-red-600 text-white animate-pulse"
                : "border-slate-200 bg-slate-50 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-600"
            } disabled:opacity-50`}
          >
            {isRecording ? (
              <Square className="h-4 w-4 fill-current" />
            ) : (
              <Mic className="h-5 w-5" />
            )}
          </button>

          {/* Text Input */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={roleConfig.placeholder}
            disabled={
              isSending || isRecording || isTranscribing || isUploadingResume
            }
            className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 disabled:opacity-50"
          />

          {/* Send Button */}
          <button
            type="submit"
            disabled={!inputText.trim() || isSending || isRecording}
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

      {role === "student" && isConsentOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-100 p-6 animate-in fade-in zoom-in-95">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 mb-4">
              <FileText className="h-6 w-6" />
            </div>

            <h3 className="text-base font-bold text-slate-900">
              Upload Resume
            </h3>

            <p className="mt-2 text-sm text-slate-600 leading-relaxed">
              We&rsquo;ll read this file to build your profile.
            </p>

            <div className="mt-3 rounded-xl bg-slate-50 p-3 text-xs text-slate-500 space-y-1.5 border border-slate-100">
              <p>
                • Supported formats: <strong>PDF</strong> or{" "}
                <strong>DOCX</strong>
              </p>
              <p>
                • Maximum file size: <strong>5 MB</strong>
              </p>
              <p>
                • Your file is parsed safely and automatically into structured
                records without forms.
              </p>
            </div>

            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setIsConsentOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConsentConfirm}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm transition"
              >
                I Agree & Choose File
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Outreach Draft Sheet Modal */}
      <DraftMessageModal
        isOpen={!!draftingContact}
        onClose={() => setDraftingContact(null)}
        contact={draftingContact}
        token={sessionToken}
        onToast={showToast}
      />
    </div>
  );
}
