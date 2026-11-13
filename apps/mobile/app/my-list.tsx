import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  StyleSheet,
  Platform,
  useWindowDimensions,
} from "react-native";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { getMobileSupabaseClient, withApiFallback } from "../lib/supabase";
import {
  ContactCard,
  listContacts,
  removeSavedContact,
  ApiError,
} from "@recruiting/shared";
import { MobileContactCard } from "./components/MobileContactCard";
import { DraftMessageSheet } from "./components/DraftMessageSheet";
import { MobileProBadge } from "./components/MobileProBadge";
import { MobileUpgradeModal } from "./components/MobileUpgradeModal";
import { syncMobileSubscription } from "../lib/subscription";
import { Feather } from "@expo/vector-icons";

export default function MyListScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const isTablet = width >= 600;
  const isSmallWidth = width < 375;

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [contacts, setContacts] = useState<ContactCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  // Draft sheet state
  const [draftingContact, setDraftingContact] = useState<ContactCard | null>(
    null
  );

  // Realtime cross-device toast
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [crossDeviceToast, setCrossDeviceToast] = useState<string | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  function showToast(text: string) {
    setCrossDeviceToast(text);
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = setTimeout(() => {
      setCrossDeviceToast(null);
    }, 4500);
  }

  // Fetch saved list
  const fetchSavedList = useCallback(async (token: string, silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const res = await withApiFallback((url) =>
        listContacts(url, token, {
          saved_only: true,
          page_size: 100,
        })
      );
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

  // 1. Authenticate & load
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setSessionToken(session.access_token);
      setUserId(session.user.id);
      supabase
        .from("profiles")
        .select("role, subscription_tier")
        .eq("id", session.user.id)
        .single()
        .then(({ data }) => {
          if (data?.role) setRole(data.role);
          if (data?.subscription_tier)
            syncMobileSubscription(data.subscription_tier);
          if (data?.subscription_tier)
            syncMobileSubscription(data.subscription_tier);
        });
      fetchSavedList(session.access_token);
    });
  }, [router, supabase, fetchSavedList]);

  // 2. Realtime sync on user_saved_contacts
  useEffect(() => {
    if (!userId || !sessionToken) return;

    // Unique per-mount suffix prevents "cannot add callbacks after subscribe()" crash
    // when navigating back to this screen without a full unmount.
    const mountId = Date.now();

    const channel = supabase
      .channel(`mobile_saved_sync_${userId}_${mountId}`)
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
            fetchSavedList(sessionToken, true);
          } else if (payload.eventType === "DELETE") {
            showToast("Contact removed from your list from your laptop");
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

  // 3. Remove action
  async function handleRemove(contactId: string) {
    if (!sessionToken || removingId) return;
    setRemovingId(contactId);
    try {
      await withApiFallback((url) =>
        removeSavedContact(url, contactId, sessionToken)
      );
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
    <SafeAreaView style={styles.safeArea}>
      <View
        style={{ flex: 1, maxWidth: 640, width: "100%", alignSelf: "center" }}
      >
        {/* Realtime Toast */}
        {crossDeviceToast && (
          <View style={styles.toastBanner}>
            <Feather name="check-circle" size={16} color="#4f46e5" />
            <View style={{ flex: 1 }}>
              <Text style={styles.toastText}>{crossDeviceToast}</Text>
              <Text style={styles.toastSub}>Synced in realtime</Text>
            </View>
            <TouchableOpacity
              onPress={() => setCrossDeviceToast(null)}
              accessibilityLabel="Dismiss toast"
            >
              <Feather name="x" size={14} color="#64748b" />
            </TouchableOpacity>
          </View>
        )}

        {/* Header */}
        <View
          style={[
            styles.header,
            { paddingHorizontal: isSmallWidth ? 12 : isTablet ? 24 : 16 },
          ]}
        >
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => router.push("/chat")}
          >
            <View
              style={{ flexDirection: "row", alignItems: "center", gap: 4 }}
            >
              <Feather name="arrow-left" size={13} color="#4f46e5" />
              <Text style={styles.backBtnText}>Chat</Text>
            </View>
          </TouchableOpacity>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Text style={styles.headerTitle}>My List</Text>
            <MobileProBadge
              role={role as any}
              onPressUpgrade={() => setShowUpgradeModal(true)}
            />
          </View>
          <TouchableOpacity
            style={styles.refreshBtn}
            onPress={() => sessionToken && fetchSavedList(sessionToken)}
            disabled={isLoading}
          >
            <Feather name="refresh-cw" size={13} color="#4338ca" />
          </TouchableOpacity>
        </View>

        {/* Main Content */}
        <View
          style={[
            styles.contentContainer,
            {
              paddingHorizontal: isSmallWidth ? 12 : isTablet ? 24 : 16,
              paddingBottom: Math.max(insets.bottom + 16, 24),
            },
          ]}
        >
          {/* Privacy Note */}
          <View style={styles.privacyBox}>
            <Feather
              name="shield"
              size={13}
              color="#64748b"
              style={{ marginTop: 2, marginRight: 6 }}
            />
            <Text style={styles.privacyText}>
              Public professional contact info only. Source and date shown for
              every record. You can remove any saved contact from My list at any
              time.
            </Text>
          </View>

          {/* Loading State */}
          {isLoading && (
            <View style={styles.centerBox}>
              <ActivityIndicator size="large" color="#4f46e5" />
              <Text style={styles.centerText}>Loading saved contacts...</Text>
            </View>
          )}

          {/* Error State */}
          {!isLoading && error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorTitle}>Could not load saved list</Text>
              <Text style={styles.errorMessage}>{error}</Text>
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={() => sessionToken && fetchSavedList(sessionToken)}
              >
                <Text style={styles.retryBtnText}>Retry</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Empty State */}
          {!isLoading && !error && contacts.length === 0 && (
            <View style={styles.emptyBox}>
              <View style={styles.emptyIconBadge}>
                <Feather name="bookmark" size={24} color="#64748b" />
              </View>
              <Text style={styles.emptyTitle}>No saved contacts yet</Text>
              <Text style={styles.emptyMessage}>
                Search for recruiters in chat and save them to your list to
                draft outreach.
              </Text>
              <TouchableOpacity
                style={styles.findBtn}
                onPress={() => router.push("/chat")}
              >
                <Text style={styles.findBtnText}>Find Recruiters in Chat</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Contacts List */}
          {!isLoading && !error && contacts.length > 0 && (
            <FlatList
              data={contacts}
              keyExtractor={(item) => item.id}
              contentContainerStyle={styles.listContent}
              renderItem={({ item }) => (
                <MobileContactCard
                  contact={item}
                  isSaved={true}
                  showRemoveOnly={true}
                  isBusy={removingId === item.id}
                  onRemove={handleRemove}
                  onDraft={(c) => setDraftingContact(c)}
                />
              )}
            />
          )}
        </View>

        {/* Draft Message Sheet */}
        <DraftMessageSheet
          visible={!!draftingContact}
          onClose={() => setDraftingContact(null)}
          contact={draftingContact}
          token={sessionToken}
          showToast={showToast}
        />

        {/* Upgrade Modal */}
        <MobileUpgradeModal
          visible={showUpgradeModal}
          onClose={() => setShowUpgradeModal(false)}
          role={role as any}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "#ffffff",
    borderBottomWidth: 1,
    borderBottomColor: "#e2e8f0",
  },
  backBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  backBtnText: {
    fontSize: 14,
    color: "#4f46e5",
    fontWeight: "600",
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0f172a",
  },
  refreshBtn: {
    padding: 6,
  },
  refreshBtnText: {
    fontSize: 18,
    color: "#64748b",
  },
  contentContainer: {
    flex: 1,
    padding: 16,
  },
  toastBanner: {
    position: "absolute",
    top: Platform.OS === "ios" ? 54 : 12,
    left: 16,
    right: 16,
    zIndex: 100,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#c7d2fe",
    borderRadius: 12,
    padding: 12,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  toastIcon: {
    fontSize: 16,
    marginRight: 8,
  },
  toastText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#1e293b",
  },
  toastSub: {
    fontSize: 10,
    color: "#64748b",
  },
  toastClose: {
    fontSize: 14,
    color: "#94a3b8",
    padding: 4,
  },
  privacyBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: "#eef2ff",
    borderWidth: 1,
    borderColor: "#e0e7ff",
    borderRadius: 10,
    padding: 10,
    marginBottom: 12,
  },
  privacyIcon: {
    fontSize: 14,
    marginRight: 8,
    marginTop: 1,
  },
  privacyText: {
    flex: 1,
    fontSize: 11,
    color: "#3730a3",
    lineHeight: 16,
  },
  centerBox: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: 40,
  },
  centerText: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 8,
  },
  errorBox: {
    backgroundColor: "#fef2f2",
    borderWidth: 1,
    borderColor: "#fecaca",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
  },
  errorTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: "#b91c1c",
  },
  errorMessage: {
    fontSize: 11,
    color: "#475569",
    textAlign: "center",
    marginTop: 4,
  },
  retryBtn: {
    backgroundColor: "#dc2626",
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 14,
    marginTop: 10,
  },
  retryBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#ffffff",
  },
  emptyBox: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: "#cbd5e1",
    borderRadius: 12,
    padding: 32,
    alignItems: "center",
    marginTop: 20,
  },
  emptyIconBadge: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: "#f1f5f9",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0f172a",
  },
  emptyMessage: {
    fontSize: 12,
    color: "#64748b",
    textAlign: "center",
    marginTop: 4,
    lineHeight: 18,
    maxWidth: 260,
  },
  findBtn: {
    backgroundColor: "#4f46e5",
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 16,
    marginTop: 16,
  },
  findBtnText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#ffffff",
  },
  listContent: {
    paddingBottom: 24,
  },
});
