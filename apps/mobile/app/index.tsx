import { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getMobileSupabaseClient } from "../lib/supabase";
import { syncMobileSubscription } from "../lib/subscription";

export default function IndexScreen() {
  const router = useRouter();

  useEffect(() => {
    async function checkAuth() {
      const demoRaw = await AsyncStorage.getItem("demo_session");
      if (demoRaw) {
        try {
          const demo = JSON.parse(demoRaw);
          if (demo.user?.role === "student") {
            router.replace("/(tabs)/home");
          } else {
            router.replace("/chat");
          }
          return;
        } catch {
          // ignore corrupted demo session
        }
      }

      const supabase = getMobileSupabaseClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) {
        router.replace("/login");
        return;
      }

      const { data: profile } = await supabase
        .from("profiles")
        .select("role, subscription_tier")
        .eq("id", session.user.id)
        .single();

      if (profile?.subscription_tier) {
        await syncMobileSubscription(profile.subscription_tier);
      }

      if (!profile || !profile.role) {
        router.replace("/onboarding");
      } else if (profile.role === "student") {
        router.replace("/(tabs)/home");
      } else {
        router.replace("/chat");
      }
    }

    checkAuth();
  }, [router]);

  return (
    <View style={styles.center}>
      <ActivityIndicator size="large" color="#4f46e5" />
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f8fafc",
  },
});
