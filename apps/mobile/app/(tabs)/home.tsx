import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { getMobileSupabaseClient, API_BASE_URL } from "../../lib/supabase";
import {
  getStudentScore,
  getStudentProfile,
  getTimeline,
  ScoreResponse,
  StudentProfile,
  TimelineStation,
} from "@recruiting/shared";
import { MobileRailwayTimeline } from "../components/MobileRailwayTimeline";
import { MobilePreVerifyModal } from "../components/MobilePreVerifyModal";
import { MobileReferenceAuthModal } from "../components/MobileReferenceAuthModal";

export default function MobileHomeScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [scoreData, setScoreData] = useState<ScoreResponse | null>(null);
  const [profileData, setProfileData] = useState<StudentProfile | null>(null);
  const [timelineStations, setTimelineStations] = useState<TimelineStation[]>(
    []
  );
  const [syncToast, setSyncToast] = useState<string | null>(null);

  // Modals state
  const [isPreVerifyVisible, setIsPreVerifyVisible] = useState(false);
  const [isRefAuthVisible, setIsRefAuthVisible] = useState(false);

  useEffect(() => {
    let isMounted = true;
    let toastTimeout: NodeJS.Timeout | null = null;

    async function loadData(token: string) {
      try {
        const [scoreRes, profRes, timelineRes] = await Promise.all([
          getStudentScore(API_BASE_URL, token),
          getStudentProfile(API_BASE_URL, token),
          getTimeline(API_BASE_URL, token).catch(() => ({ stations: [] })),
        ]);

        if (isMounted) {
          setScoreData(scoreRes);
          setProfileData(profRes);
          setTimelineStations(timelineRes.stations || []);
          setLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Failed to load profile.");
          setLoading(false);
        }
      }
    }

    let channels: any[] = [];

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }

      const token = session.access_token;
      const userId = session.user.id;
      setSessionToken(token);
      loadData(token);

      const triggerToastAndReload = (msg = "Updated from your laptop") => {
        if (!isMounted) return;
        setSyncToast(msg);
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
          if (isMounted) setSyncToast(null);
        }, 4000);
        loadData(token);
      };

      const scoreChan = supabase
        .channel(`mobile_home_score_${userId}`)
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
            triggerToastAndReload(
              sc !== undefined
                ? `Score updated to ${sc} from your laptop`
                : "Updated from your laptop"
            );
          }
        )
        .subscribe();

      const profChan = supabase
        .channel(`mobile_home_profile_${userId}`)
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "education",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Profile updated from your laptop")
        )
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "internships",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Profile updated from your laptop")
        )
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "skills",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Profile updated from your laptop")
        )
        .on(
          "postgres_changes",
          {
            event: "*",
            schema: "public",
            table: "reference_authorizations",
            filter: `profile_id=eq.${userId}`,
          },
          () => triggerToastAndReload("Reference check authorization updated")
        )
        .subscribe();

      channels = [scoreChan, profChan];
    });

    return () => {
      isMounted = false;
      if (toastTimeout) clearTimeout(toastTimeout);
      channels.forEach((c) => supabase.removeChannel(c));
    };
  }, [router, supabase]);

  if (loading) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2563EB" />
        <Text style={styles.loadingText}>Loading readiness profile...</Text>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => router.push("/chat")}
        >
          <Text style={styles.actionButtonText}>Go to Chat</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const score = scoreData?.score ?? 20;
  const breakdown = scoreData?.breakdown ?? [];
  const nextActions = scoreData?.next_best_actions ?? [];

  const student = profileData?.student;
  const internships = profileData?.internships ?? [];
  const documents = profileData?.documents ?? [];

  // Day 5 status flags
  const verifiedDoc = documents.find((d) => d.verified_flag);
  const isPreVerified =
    !!verifiedDoc ||
    breakdown.some(
      (b) =>
        b.reason.toLowerCase().includes("pre-verified") ||
        b.reason.toLowerCase().includes("identity document")
    );
  const hasUploadedDocs = documents.length > 0;
  const maskedTail = verifiedDoc?.masked_id_tail;

  const isRefAuthorized = breakdown.some(
    (b) =>
      b.reason.toLowerCase().includes("reference check") ||
      b.reason.toLowerCase().includes("reference-check")
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* Realtime Sync Toast */}
      {syncToast && (
        <View style={styles.toastContainer}>
          <Text style={styles.toastIcon}>💻</Text>
          <View style={{ flex: 1 }}>
            <Text style={styles.toastTitle}>{syncToast}</Text>
            <Text style={styles.toastSubtitle}>Synced live from laptop</Text>
          </View>
          <TouchableOpacity onPress={() => setSyncToast(null)}>
            <Text style={styles.toastClose}>✕</Text>
          </TouchableOpacity>
        </View>
      )}

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>Student Dashboard</Text>
            <Text style={styles.headerSubtitle}>
              {student?.full_name
                ? `${student.full_name} • Batch ${student.batch_year}`
                : "NextStop Recruiting"}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.chatHeaderButton}
            onPress={() => router.push("/chat")}
          >
            <Text style={styles.chatHeaderButtonText}>Chat</Text>
          </TouchableOpacity>
        </View>

        {/* Score Card */}
        <View style={styles.scoreCard}>
          <Text style={styles.scoreCardLabel}>CAMPUS READINESS SCORE</Text>
          <View style={styles.scoreRow}>
            <Text style={styles.scoreNumber}>{score}</Text>
            <Text style={styles.scoreMax}>/ 100</Text>
          </View>
          <View style={styles.progressBarBg}>
            <View
              style={[
                styles.progressBarFill,
                { width: `${Math.min(100, Math.max(0, score))}%` },
              ]}
            />
          </View>
        </View>

        {/* Next Best Action Card */}
        {nextActions.length > 0 && (
          <View style={styles.nextActionCard}>
            <Text style={styles.nextActionLabel}>NEXT BEST ACTION</Text>
            <Text style={styles.nextActionText}>{nextActions[0]}</Text>
            <TouchableOpacity onPress={() => router.push("/chat")}>
              <Text style={styles.nextActionLink}>Complete now in chat →</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Day 5 Pre-Verification Action Card */}
        <View style={styles.sectionCard}>
          <View style={styles.day5HeaderRow}>
            <View style={styles.day5TitleGroup}>
              <Text style={styles.day5Icon}>🛡️</Text>
              <View>
                <Text style={styles.sectionTitle}>
                  Document Pre-Verification
                </Text>
                <Text style={styles.day5Sub}>Demo verification (mocked)</Text>
              </View>
            </View>
            {isPreVerified ? (
              <View style={[styles.statusChip, styles.chipGreen]}>
                <Text style={styles.chipTextGreen}>✓ Verified (mocked)</Text>
              </View>
            ) : hasUploadedDocs ? (
              <View style={[styles.statusChip, styles.chipBlue]}>
                <Text style={styles.chipTextBlue}>Uploaded</Text>
              </View>
            ) : (
              <View style={[styles.statusChip, styles.chipGray]}>
                <Text style={styles.chipTextGray}>Not verified</Text>
              </View>
            )}
          </View>

          {maskedTail && (
            <View style={styles.maskedContainer}>
              <Text style={styles.maskedLabelText}>Masked ID Identifier:</Text>
              <Text style={styles.maskedValueText}>{maskedTail}</Text>
            </View>
          )}

          <Text style={styles.day5Explainer}>
            Pre-verify your sample credentials to claim +2 readiness points. The
            app never reads file contents or authentic ID numbers.
          </Text>

          <View style={styles.day5ActionFooter}>
            <Text style={styles.pointsNoticeIndigo}>
              {isPreVerified ? "+2 points awarded" : "+2 points available"}
            </Text>
            <TouchableOpacity
              style={styles.day5ButtonIndigo}
              onPress={() => setIsPreVerifyVisible(true)}
            >
              <Text style={styles.day5ButtonText}>
                {isPreVerified ? "Manage Documents" : "Pre-Verify Document"}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Day 5 Reference Check Action Card */}
        <View style={styles.sectionCard}>
          <View style={styles.day5HeaderRow}>
            <View style={styles.day5TitleGroup}>
              <Text style={styles.day5Icon}>🎖️</Text>
              <View>
                <Text style={styles.sectionTitle}>Reference Check</Text>
                <Text style={styles.day5Sub}>Internship employer outreach</Text>
              </View>
            </View>
            {isRefAuthorized ? (
              <View style={[styles.statusChip, styles.chipGreen]}>
                <Text style={styles.chipTextGreen}>✓ Authorized</Text>
              </View>
            ) : (
              <View style={[styles.statusChip, styles.chipGray]}>
                <Text style={styles.chipTextGray}>Not authorized</Text>
              </View>
            )}
          </View>

          <Text style={styles.day5Explainer}>
            Authorizing lets verified recruiters and placement officers contact
            your internship company to confirm your experience.
          </Text>

          <View style={styles.day5ActionFooter}>
            <Text style={styles.pointsNoticeAmber}>
              {isRefAuthorized ? "+2 points awarded" : "+2 points available"}
            </Text>
            <TouchableOpacity
              style={styles.day5ButtonAmber}
              onPress={() => setIsRefAuthVisible(true)}
            >
              <Text style={styles.day5ButtonText}>
                {isRefAuthorized
                  ? "Manage Authorization"
                  : "Authorize Outreach"}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Why is my score N? */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionTitle}>Why is my score {score}?</Text>
          {breakdown.map((item, idx) => {
            const isPreVerify =
              item.reason.toLowerCase().includes("pre-verified") ||
              item.reason.toLowerCase().includes("identity document");

            return (
              <View key={idx} style={styles.breakdownRow}>
                <View style={styles.breakdownLeft}>
                  <View
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: 4,
                    }}
                  >
                    <Text style={styles.breakdownReason}>{item.reason}</Text>
                    {isPreVerify && (
                      <View style={styles.mockBadge}>
                        <Text style={styles.mockBadgeText}>
                          Demo verification (mocked)
                        </Text>
                      </View>
                    )}
                  </View>
                  <Text style={styles.breakdownSource}>
                    source: {item.source}
                  </Text>
                </View>
                <Text style={styles.breakdownPoints}>+{item.points}</Text>
              </View>
            );
          })}
        </View>

        {/* Railway Timeline from GET /v1/students/me/timeline */}
        <View style={styles.sectionCard}>
          <View style={{ marginBottom: 12 }}>
            <Text style={styles.sectionTitle}>Railway Career Journey</Text>
            <Text style={styles.day5Sub}>
              Stations chronologically ordered along your professional route
            </Text>
          </View>

          <MobileRailwayTimeline
            stations={timelineStations}
            isLoading={loading}
          />
        </View>
      </ScrollView>

      {/* Pre-Verify Modal */}
      <MobilePreVerifyModal
        visible={isPreVerifyVisible}
        onClose={() => setIsPreVerifyVisible(false)}
        token={sessionToken || ""}
        baseUrl={API_BASE_URL}
        documents={documents}
        onSuccess={(sc) => {
          if (sc) setScoreData(sc);
          if (sessionToken) {
            getStudentProfile(API_BASE_URL, sessionToken)
              .then(setProfileData)
              .catch(() => {});
            getTimeline(API_BASE_URL, sessionToken)
              .then((t) => setTimelineStations(t.stations || []))
              .catch(() => {});
          }
        }}
      />

      {/* Reference Check Modal */}
      <MobileReferenceAuthModal
        visible={isRefAuthVisible}
        onClose={() => setIsRefAuthVisible(false)}
        token={sessionToken || ""}
        baseUrl={API_BASE_URL}
        internships={internships}
        isAuthorized={isRefAuthorized}
        onSuccess={(sc) => {
          if (sc) setScoreData(sc);
          if (sessionToken) {
            getTimeline(API_BASE_URL, sessionToken)
              .then((t) => setTimelineStations(t.stations || []))
              .catch(() => {});
          }
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
    backgroundColor: "#F8FAFC",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: "#64748B",
  },
  errorText: {
    color: "#EF4444",
    fontSize: 14,
    textAlign: "center",
    marginBottom: 16,
  },
  actionButton: {
    backgroundColor: "#2563EB",
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
  },
  actionButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "600",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#0F172A",
  },
  headerSubtitle: {
    fontSize: 12,
    color: "#64748B",
    marginTop: 2,
  },
  chatHeaderButton: {
    backgroundColor: "#2563EB",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  chatHeaderButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "600",
  },
  scoreCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 18,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  scoreCardLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: "#64748B",
    letterSpacing: 0.8,
  },
  scoreRow: {
    flexDirection: "row",
    alignItems: "baseline",
    marginTop: 8,
    gap: 4,
  },
  scoreNumber: {
    fontSize: 44,
    fontWeight: "800",
    color: "#2563EB",
  },
  scoreMax: {
    fontSize: 14,
    fontWeight: "600",
    color: "#94A3B8",
  },
  progressBarBg: {
    height: 8,
    backgroundColor: "#F1F5F9",
    borderRadius: 4,
    marginTop: 12,
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    backgroundColor: "#2563EB",
    borderRadius: 4,
  },
  nextActionCard: {
    backgroundColor: "#EFF6FF",
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#BFDBFE",
  },
  nextActionLabel: {
    fontSize: 10,
    fontWeight: "700",
    color: "#1D4ED8",
    letterSpacing: 0.8,
  },
  nextActionText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#1E293B",
    marginTop: 6,
    lineHeight: 18,
  },
  nextActionLink: {
    fontSize: 12,
    fontWeight: "700",
    color: "#2563EB",
    marginTop: 10,
  },
  sectionCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0F172A",
  },
  day5HeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  day5TitleGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  day5Icon: {
    fontSize: 20,
  },
  day5Sub: {
    fontSize: 10,
    color: "#64748B",
    marginTop: 1,
  },
  statusChip: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  chipGreen: {
    backgroundColor: "#ECFDF5",
    borderWidth: 1,
    borderColor: "#A7F3D0",
  },
  chipTextGreen: {
    fontSize: 10,
    fontWeight: "700",
    color: "#065F46",
  },
  chipBlue: {
    backgroundColor: "#EFF6FF",
    borderWidth: 1,
    borderColor: "#BFDBFE",
  },
  chipTextBlue: {
    fontSize: 10,
    fontWeight: "700",
    color: "#1D4ED8",
  },
  chipGray: {
    backgroundColor: "#F1F5F9",
  },
  chipTextGray: {
    fontSize: 10,
    fontWeight: "600",
    color: "#64748B",
  },
  maskedContainer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#F8FAFC",
    borderRadius: 8,
    padding: 8,
    marginTop: 10,
    borderWidth: 1,
    borderColor: "#E2E8F0",
  },
  maskedLabelText: {
    fontSize: 10,
    color: "#64748B",
  },
  maskedValueText: {
    fontSize: 11,
    fontWeight: "700",
    fontFamily: "monospace",
    color: "#0F172A",
  },
  day5Explainer: {
    fontSize: 11,
    color: "#475569",
    marginTop: 8,
    lineHeight: 15,
  },
  day5ActionFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: "#F1F5F9",
  },
  pointsNoticeIndigo: {
    fontSize: 11,
    fontWeight: "700",
    color: "#4F46E5",
  },
  pointsNoticeAmber: {
    fontSize: 11,
    fontWeight: "700",
    color: "#D97706",
  },
  day5ButtonIndigo: {
    backgroundColor: "#4F46E5",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  day5ButtonAmber: {
    backgroundColor: "#D97706",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  day5ButtonText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "700",
  },
  breakdownRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#F1F5F9",
  },
  breakdownLeft: {
    flex: 1,
    paddingRight: 8,
  },
  breakdownReason: {
    fontSize: 12,
    fontWeight: "600",
    color: "#1E293B",
  },
  mockBadge: {
    backgroundColor: "#EEF2FF",
    borderWidth: 1,
    borderColor: "#C7D2FE",
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 4,
  },
  mockBadgeText: {
    fontSize: 9,
    color: "#4338CA",
    fontWeight: "700",
  },
  breakdownSource: {
    fontSize: 10,
    color: "#94A3B8",
    marginTop: 2,
  },
  breakdownPoints: {
    fontSize: 13,
    fontWeight: "700",
    color: "#059669",
  },
  toastContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#BFDBFE",
    padding: 12,
    marginHorizontal: 16,
    marginTop: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  toastIcon: {
    fontSize: 18,
  },
  toastTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: "#0F172A",
  },
  toastSubtitle: {
    fontSize: 10,
    color: "#64748B",
  },
  toastClose: {
    fontSize: 14,
    color: "#94A3B8",
    padding: 4,
  },
});
