import React, { useEffect, useState } from "react";
import { View, Text, ActivityIndicator, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import * as Linking from "expo-linking";
import { getMobileSupabaseClient } from "../../lib/supabase";

export default function AuthCallback() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function handleDeepLink() {
      try {
        const url = await Linking.getInitialURL();
        if (url) {
          const parsed = Linking.parse(url);
          const code = parsed.queryParams?.code;
          if (code && typeof code === "string") {
            const { error } = await supabase.auth.exchangeCodeForSession(code);
            if (error) throw error;
          }

          if (url.includes("#")) {
            const hashPart = url.split("#")[1];
            const params = new URLSearchParams(hashPart);
            const access_token = params.get("access_token");
            const refresh_token = params.get("refresh_token");
            if (access_token && refresh_token) {
              const { error } = await supabase.auth.setSession({
                access_token,
                refresh_token,
              });
              if (error) throw error;
            }
          }
        }

        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (!session) {
          if (isMounted) router.replace("/login");
          return;
        }

        const { data: profile } = await supabase
          .from("profiles")
          .select("role")
          .eq("id", session.user.id)
          .single();

        if (!isMounted) return;

        if (!profile || !profile.role) {
          router.replace("/onboarding");
        } else if (profile.role === "student") {
          router.replace("/(tabs)/home");
        } else {
          router.replace("/chat");
        }
      } catch (err: any) {
        if (isMounted) {
          setErrorMsg(
            err.message || "Authentication failed. Redirecting to login..."
          );
          setTimeout(() => router.replace("/login"), 2000);
        }
      }
    }

    handleDeepLink();

    return () => {
      isMounted = false;
    };
  }, [router, supabase]);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#4f46e5" />
      <Text style={styles.text}>
        {errorMsg ? errorMsg : "Completing Google sign in..."}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f8fafc",
    padding: 20,
  },
  text: {
    marginTop: 16,
    fontSize: 14,
    color: "#64748b",
    textAlign: "center",
  },
});
