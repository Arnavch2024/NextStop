import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  useWindowDimensions,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { getMobileSupabaseClient } from "../lib/supabase";
import { ProfileRole } from "@recruiting/shared";

interface RoleCard {
  role: ProfileRole;
  title: string;
  badge: string;
  desc: string;
}

const ROLES: RoleCard[] = [
  {
    role: "student",
    title: "Student",
    badge: "Batch 2027 / 2028",
    desc: "Mumbai college student discovering placements & self-reporting details.",
  },
  {
    role: "placement_officer",
    title: "Placement Officer",
    badge: "Placement Cell",
    desc: "Managing college profile, departments, and cohort student records.",
  },
  {
    role: "company",
    title: "Company",
    badge: "Hiring Org",
    desc: "Register hiring company details and recruiting coordinators.",
  },
  {
    role: "recruiter",
    title: "Recruiter",
    badge: "Talent Acquisition",
    desc: "Recruiter connecting student talent with top hiring organizations.",
  },
];

export default function OnboardingScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();

  const isSmallWidth = width < 375;
  const isTablet = width >= 600;
  const isCompactHeight = height < 700;

  const [loadingRole, setLoadingRole] = useState<ProfileRole | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }
      setUserId(session.user.id);
    });
  }, [router, supabase]);

  async function handleSelect(role: ProfileRole) {
    if (!userId) return;
    setLoadingRole(role);

    try {
      const { error } = await supabase.from("profiles").upsert({
        id: userId,
        role,
        updated_at: new Date().toISOString(),
      });

      if (error) throw error;
      router.replace("/chat");
    } catch {
      setLoadingRole(null);
    }
  }

  return (
    <ScrollView
      contentContainerStyle={[
        styles.container,
        {
          paddingTop: Math.max(insets.top + 12, 20),
          paddingBottom: Math.max(insets.bottom + 20, 28),
          paddingHorizontal: isSmallWidth ? 16 : isTablet ? 36 : 24,
          justifyContent: isCompactHeight ? "flex-start" : "center",
        },
      ]}
      showsVerticalScrollIndicator={false}
    >
      <View
        style={[
          styles.innerWrapper,
          { maxWidth: 480, width: "100%", alignSelf: "center" },
        ]}
      >
        <View style={[styles.header, isSmallWidth && { marginBottom: 16 }]}>
          <Text style={styles.badge}>Step 1 of 1</Text>
          <Text style={[styles.title, isSmallWidth && { fontSize: 22 }]}>
            Choose Your Role
          </Text>
          <Text style={[styles.subtitle, isSmallWidth && { fontSize: 12 }]}>
            One tap sets your profile. Everything else is conversational.
          </Text>
        </View>

        <View style={styles.grid}>
          {ROLES.map((r) => {
            const isLoading = loadingRole === r.role;
            return (
              <TouchableOpacity
                key={r.role}
                style={[styles.card, isSmallWidth && { padding: 14 }]}
                onPress={() => handleSelect(r.role)}
                disabled={loadingRole !== null}
              >
                <View style={styles.cardTop}>
                  <Text
                    style={[styles.cardTitle, isSmallWidth && { fontSize: 15 }]}
                  >
                    {r.title}
                  </Text>
                  <Text style={styles.cardBadge}>{r.badge}</Text>
                </View>
                <Text
                  style={[
                    styles.cardDesc,
                    isSmallWidth && { fontSize: 12, lineHeight: 16 },
                  ]}
                >
                  {r.desc}
                </Text>

                <View
                  style={[styles.cardBottom, isSmallWidth && { marginTop: 8 }]}
                >
                  {isLoading ? (
                    <ActivityIndicator size="small" color="#4f46e5" />
                  ) : (
                    <Text style={styles.selectText}>Select &rarr;</Text>
                  )}
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#f8fafc",
    flexGrow: 1,
  },
  innerWrapper: {
    flex: 1,
    justifyContent: "center",
  },
  header: {
    alignItems: "center",
    marginBottom: 24,
  },
  badge: {
    color: "#4f46e5",
    backgroundColor: "#eef2ff",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    fontSize: 11,
    fontWeight: "700",
    overflow: "hidden",
  },
  title: {
    fontSize: 26,
    fontWeight: "800",
    color: "#0f172a",
    marginTop: 8,
  },
  subtitle: {
    fontSize: 13,
    color: "#64748b",
    marginTop: 4,
    textAlign: "center",
  },
  grid: {
    gap: 12,
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: 16,
    padding: 18,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  cardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  cardTitle: {
    fontSize: 17,
    fontWeight: "700",
    color: "#0f172a",
  },
  cardBadge: {
    fontSize: 11,
    color: "#475569",
    backgroundColor: "#f1f5f9",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    overflow: "hidden",
  },
  cardDesc: {
    fontSize: 13,
    color: "#64748b",
    lineHeight: 18,
  },
  cardBottom: {
    marginTop: 12,
    alignItems: "flex-end",
  },
  selectText: {
    color: "#4f46e5",
    fontSize: 13,
    fontWeight: "700",
  },
});
