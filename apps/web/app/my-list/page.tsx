"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSupabaseBrowserClient, API_BASE_URL } from "@/lib/supabase";
import {
  ContactCard,
  listContacts,
  removeSavedContact,
  ApiError,
} from "@recruiting/shared";
import { ContactCardItem } from "@/app/components/ContactCardItem";
import { DraftMessageModal } from "@/app/components/DraftMessageModal";
import { SwitchDemoRoleButton } from "@/app/components/SwitchDemoRoleButton";
import { DownloadAppButton } from "@/app/components/DownloadAppButton";
import {
  Bookmark,
  MessageSquare,
  ArrowLeft,
  Loader2,
  AlertCircle,
  ShieldCheck,
  X,
  Smartphone,
  RefreshCw,
  Search,
} from "lucide-react";

export default function MyListPage() {
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [isDemo, setIsDemo] = useState(false);

  const [contacts, setContacts] = useState<ContactCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  // Draft modal state
  const [draftingContact, setDraftingContact] = useState<ContactCard | null>(
    null
  );

  // Cross-device sync toast state
  const [crossDeviceToast, setCrossDeviceToast] = useState<string | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  function showToast(message: string) {
    setCrossDeviceToast(message);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = setTimeout(() => {
      setCrossDeviceToast(null);
    }, 4500);
  }

  // Fetch saved contacts list
  const fetchSavedList = useCallback(async (token: string, silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const res = await listContacts(API_BASE_URL, token, {
        saved_only: true,
        page_size: 100,
      });
      setContacts(res.items || []);
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 429) {
        setError(
          "Rate limit reached. Please wait a moment before trying again."
        );
      } else {
        setError(err?.message || "Failed to load saved contacts list.");
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  // 1. Check Session & Load
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
      if (profile.is_demo) {
        setIsDemo(true);
      }
      setDisplayName(
        profile.display_name || session.user.email?.split("@")[0] || "User"
      );

      fetchSavedList(session.access_token);
    });
  }, [router, supabase, fetchSavedList]);

  // 2. Realtime sync on user_saved_contacts
  useEffect(() => {
    if (!userId || !sessionToken) return;

    const chanId = Math.random().toString(36).slice(2, 7);
    const channel = supabase
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
            fetchSavedList(sessionToken, true);
          } else if (payload.eventType === "DELETE") {
            showToast("Contact removed from your list from your phone");
            fetchSavedList(sessionToken, true);
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, [userId, sessionToken, supabase, fetchSavedList]);

  // 3. Remove contact action
  async function handleRemoveContact(contactId: string) {
    if (!sessionToken || removingId) return;
    setRemovingId(contactId);
    try {
      await removeSavedContact(API_BASE_URL, contactId, sessionToken);
      setContacts((prev) => prev.filter((c) => c.id !== contactId));
      showToast("Contact removed from your list");
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 429) {
        showToast("Rate limit reached. Please wait a moment.");
      } else {
        showToast(err?.message || "Failed to remove contact");
      }
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-slate-50 font-sans text-slate-800">
      {/* Realtime Toast */}
      {crossDeviceToast && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-2.5 rounded-xl border border-indigo-200 bg-white px-4 py-3 text-xs font-medium text-slate-800 shadow-xl animate-in fade-in slide-in-from-top-4">
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

      {/* Top Header */}
      <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
        <div className="flex items-center gap-3">
          <Link
            href="/chat"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-800 transition"
            title="Back to Chat"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
            <Bookmark className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900">My List</h1>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">{displayName}</span>
              <span className="rounded-full bg-indigo-50 px-2 py-0.2 text-[10px] font-semibold text-indigo-700 capitalize">
                {role?.replace("_", " ")}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <DownloadAppButton variant="header" />
          {isDemo && <SwitchDemoRoleButton />}
          <button
            type="button"
            onClick={() => sessionToken && fetchSavedList(sessionToken)}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition disabled:opacity-50"
            title="Refresh list"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`}
            />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          <Link
            href="/chat"
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 transition shadow-2xs"
          >
            <MessageSquare className="h-3.5 w-3.5" />
            <span>Chat Agent</span>
          </Link>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {/* Section Header & Count */}
          <div className="flex items-center justify-between pb-2">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Saved Contacts ({contacts.length})
              </h2>
              <p className="text-xs text-slate-500">
                Private to your account. Realtime synchronized across your
                devices.
              </p>
            </div>
          </div>

          {/* Short Privacy Note */}
          <div className="flex items-start gap-2.5 rounded-xl border border-indigo-100 bg-indigo-50/60 p-3.5 text-xs text-indigo-950">
            <ShieldCheck className="h-4 w-4 shrink-0 text-indigo-600 mt-0.5" />
            <p className="leading-relaxed">
              Public professional contact info only. Source and date shown for
              every record. You can remove any saved contact from My list at any
              time.
            </p>
          </div>

          {/* Loading State */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
              <p className="mt-3 text-xs font-medium text-slate-600">
                Loading your saved contacts...
              </p>
            </div>
          )}

          {/* Error State */}
          {!isLoading && error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-xs text-red-700">
              <AlertCircle className="mx-auto h-8 w-8 text-red-500" />
              <p className="mt-2 font-semibold text-sm">
                Could not load your saved list
              </p>
              <p className="mt-1 text-slate-600">{error}</p>
              <button
                type="button"
                onClick={() => sessionToken && fetchSavedList(sessionToken)}
                className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700 transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

          {/* Empty State */}
          {!isLoading && !error && contacts.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                <Bookmark className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-sm font-bold text-slate-800">
                No saved contacts yet
              </h3>
              <p className="mx-auto mt-1 max-w-sm text-xs text-slate-500">
                Search for campus recruiters or companies in chat, and save them
                to your personal list to draft outreach messages.
              </p>
              <div className="mt-5">
                <Link
                  href="/chat"
                  className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-indigo-700 transition"
                >
                  <Search className="h-3.5 w-3.5" />
                  <span>Find Recruiters in Chat</span>
                </Link>
              </div>
            </div>
          )}

          {/* Contact Cards List */}
          {!isLoading && !error && contacts.length > 0 && (
            <div className="space-y-3">
              {contacts.map((contact) => (
                <ContactCardItem
                  key={contact.id}
                  contact={contact}
                  isSaved={true}
                  showRemoveOnly={true}
                  isBusy={removingId === contact.id}
                  onRemove={handleRemoveContact}
                  onDraft={(c) => setDraftingContact(c)}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Outreach Draft Message Sheet Modal */}
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
