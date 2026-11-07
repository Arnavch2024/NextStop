import { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { getMobileSupabaseClient } from "../lib/supabase";

export default function IndexScreen() {
  const router = useRouter();

  useEffect(() => {
    const supabase = getMobileSupabaseClient();
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.replace("/login");
        return;
      }

      const { data: profile } = await supabase
        .from("profiles")
        .select("role")
        .eq("id", session.user.id)
        .single();

      if (!profile || !profile.role) {
        router.replace("/onboarding");
      } else {
        router.replace("/chat");
      }
    });
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
