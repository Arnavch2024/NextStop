import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getMobileSupabaseClient, API_BASE_URL } from "../lib/supabase";
import { demoLogin } from "@recruiting/shared";

export default function LoginScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [useMagicLink, setUseMagicLink] = useState(false);
  const [loading, setLoading] = useState(false);
  const [demoRoleLoading, setDemoRoleLoading] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);

  async function handleAuth() {
    if (!email) return;
    setLoading(true);
    setErrorMsg(null);
    setInfoMsg(null);

    try {
      await AsyncStorage.removeItem("demo_session");

      if (useMagicLink) {
        const { error } = await supabase.auth.signInWithOtp({ email });
        if (error) throw error;
        setInfoMsg("Magic link sent to your email! Please open it to sign in.");
      } else if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;

        if (data.session) {
          router.replace("/onboarding");
        } else {
          setInfoMsg("Account created! Please check your email to verify.");
        }
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;

        const { data: profile } = await supabase
          .from("profiles")
          .select("role")
          .eq("id", data.user.id)
          .single();

        if (!profile || !profile.role) {
          router.replace("/onboarding");
        } else if (profile.role === "student") {
          router.replace("/(tabs)/home");
        } else {
          router.replace("/chat");
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDemoLogin(role: string) {
    setDemoRoleLoading(role);
    setErrorMsg(null);
    try {
      const res = await demoLogin(API_BASE_URL, role);
      if (res.access_token && res.refresh_token) {
        await supabase.auth.setSession({
          access_token: res.access_token,
          refresh_token: res.refresh_token,
        });
      }
      if (role === "student") {
        router.replace("/(tabs)/home");
      } else {
        router.replace("/chat");
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Demo login failed");
    } finally {
      setDemoRoleLoading(null);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.card}>
          <Text style={styles.title}>Campus Recruiting</Text>
          <Text style={styles.subtitle}>
            Mumbai College Batches 2027 & 2028
          </Text>

          {errorMsg && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{errorMsg}</Text>
            </View>
          )}

          {infoMsg && (
            <View style={styles.infoBox}>
              <Text style={styles.infoText}>{infoMsg}</Text>
            </View>
          )}

          <Text style={styles.label}>EMAIL ADDRESS</Text>
          <TextInput
            style={styles.input}
            autoCapitalize="none"
            keyboardType="email-address"
            value={email}
            onChangeText={setEmail}
            placeholder="name@college.edu or company.com"
            placeholderTextColor="#94a3b8"
          />

          {!useMagicLink && (
            <>
              <Text style={styles.label}>PASSWORD</Text>
              <TextInput
                style={styles.input}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
                placeholder="••••••••"
                placeholderTextColor="#94a3b8"
              />
            </>
          )}

          <TouchableOpacity
            style={[styles.button, loading && styles.buttonDisabled]}
            disabled={loading}
            onPress={handleAuth}
          >
            {loading ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <Text style={styles.buttonText}>
                {useMagicLink
                  ? "Send Magic Link"
                  : isSignUp
                    ? "Create Account"
                    : "Sign In"}
              </Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.switchButton}
            onPress={() => setUseMagicLink(!useMagicLink)}
          >
            <Text style={styles.switchText}>
              {useMagicLink
                ? "Sign in with Password instead"
                : "Sign in with Magic Link"}
            </Text>
          </TouchableOpacity>

          {!useMagicLink && (
            <TouchableOpacity
              style={styles.switchButton}
              onPress={() => setIsSignUp(!isSignUp)}
            >
              <Text style={styles.switchSubtext}>
                {isSignUp
                  ? "Already have an account? Sign In"
                  : "Don't have an account? Sign Up"}
              </Text>
            </TouchableOpacity>
          )}

          {/* Quick Demo Access Buttons */}
          <View style={styles.demoSection}>
            <Text style={styles.demoHeader}>TRY DEMO PERSONAS</Text>
            <View style={styles.demoGrid}>
              {[
                { role: "placement_officer", label: "Placement Officer" },
                { role: "company", label: "Company HR" },
                { role: "recruiter", label: "Talent Recruiter" },
                { role: "student", label: "Student" },
              ].map((item) => (
                <TouchableOpacity
                  key={item.role}
                  style={styles.demoButton}
                  disabled={demoRoleLoading !== null}
                  onPress={() => handleDemoLogin(item.role)}
                >
                  {demoRoleLoading === item.role ? (
                    <ActivityIndicator size="small" color="#4f46e5" />
                  ) : (
                    <Text style={styles.demoButtonText}>{item.label}</Text>
                  )}
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
  scroll: {
    flexGrow: 1,
    justifyContent: "center",
    padding: 20,
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: 20,
    padding: 24,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    color: "#0f172a",
    textAlign: "center",
  },
  subtitle: {
    fontSize: 13,
    color: "#64748b",
    textAlign: "center",
    marginTop: 4,
    marginBottom: 20,
  },
  label: {
    fontSize: 11,
    fontWeight: "700",
    color: "#475569",
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    color: "#0f172a",
  },
  button: {
    backgroundColor: "#4f46e5",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 20,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  switchButton: {
    marginTop: 14,
    alignItems: "center",
  },
  switchText: {
    color: "#4f46e5",
    fontSize: 13,
    fontWeight: "600",
  },
  switchSubtext: {
    color: "#64748b",
    fontSize: 12,
  },
  errorBox: {
    backgroundColor: "#fef2f2",
    padding: 10,
    borderRadius: 8,
    marginBottom: 10,
  },
  errorText: {
    color: "#dc2626",
    fontSize: 13,
  },
  infoBox: {
    backgroundColor: "#ecfdf5",
    padding: 10,
    borderRadius: 8,
    marginBottom: 10,
  },
  infoText: {
    color: "#047857",
    fontSize: 13,
  },
  demoSection: {
    marginTop: 24,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: "#f1f5f9",
  },
  demoHeader: {
    fontSize: 10,
    fontWeight: "700",
    color: "#64748b",
    letterSpacing: 0.5,
    textAlign: "center",
    marginBottom: 10,
  },
  demoGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    justifyContent: "space-between",
  },
  demoButton: {
    width: "48%",
    backgroundColor: "#eef2ff",
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 8,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#c7d2fe",
  },
  demoButtonText: {
    color: "#4338ca",
    fontSize: 11,
    fontWeight: "600",
  },
});
