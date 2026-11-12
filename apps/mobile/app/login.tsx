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
  useWindowDimensions,
} from "react-native";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getMobileSupabaseClient, withApiFallback } from "../lib/supabase";
import { demoLogin } from "@recruiting/shared";

WebBrowser.maybeCompleteAuthSession();

const DEMO_CREDENTIALS: Record<string, { email: string; password: string }> = {
  placement_officer: {
    email: "demo-officer@example.com",
    password: "DemoSecret123!",
  },
  company: { email: "demo-company@example.com", password: "DemoSecret123!" },
  recruiter: {
    email: "demo-recruiter@example.com",
    password: "DemoSecret123!",
  },
  student: { email: "demo-student@example.com", password: "DemoSecret123!" },
};

export default function LoginScreen() {
  const router = useRouter();
  const supabase = getMobileSupabaseClient();
  const { width, height } = useWindowDimensions();
  const insets = useSafeAreaInsets();

  const isSmallWidth = width < 375;
  const isTablet = width >= 600;
  const isCompactHeight = height < 740;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [useMagicLink, setUseMagicLink] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
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

  async function handleGoogleLogin() {
    setGoogleLoading(true);
    setErrorMsg(null);
    setInfoMsg(null);
    try {
      const redirectUrl = Linking.createURL("auth/callback");
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: redirectUrl,
          skipBrowserRedirect: true,
        },
      });

      if (error) throw error;
      if (!data?.url) {
        throw new Error("No authorization URL returned from Supabase.");
      }

      const res = await WebBrowser.openAuthSessionAsync(data.url, redirectUrl);

      if (res.type === "success" && res.url) {
        const parsed = Linking.parse(res.url);
        const code = parsed.queryParams?.code;
        if (code && typeof code === "string") {
          const { error: exchangeError } =
            await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) throw exchangeError;
        }

        if (res.url.includes("#")) {
          const hashPart = res.url.split("#")[1];
          const params = new URLSearchParams(hashPart);
          const access_token = params.get("access_token");
          const refresh_token = params.get("refresh_token");
          if (access_token && refresh_token) {
            const { error: sessionError } = await supabase.auth.setSession({
              access_token,
              refresh_token,
            });
            if (sessionError) throw sessionError;
          }
        }

        const {
          data: { session },
        } = await supabase.auth.getSession();

        if (session) {
          const { data: profile } = await supabase
            .from("profiles")
            .select("role")
            .eq("id", session.user.id)
            .single();

          if (!profile || !profile.role) {
            router.replace("/onboarding");
          } else if (profile.role === "student") {
            router.replace("/(tabs)/home");
          } else {
            router.replace("/chat");
          }
        }
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Google sign in failed.");
    } finally {
      setGoogleLoading(false);
    }
  }

  async function handleDemoLogin(role: string) {
    setDemoRoleLoading(role);
    setErrorMsg(null);
    try {
      let loggedIn = false;

      // 1. Attempt API demo-login endpoint first with auto-discovery failover
      try {
        const res = await withApiFallback((url) => demoLogin(url, role));
        if (res.access_token && res.refresh_token) {
          await supabase.auth.setSession({
            access_token: res.access_token,
            refresh_token: res.refresh_token,
          });
          loggedIn = true;
        }
      } catch (apiErr) {
        // Fallback directly to Supabase cloud auth if local API server is unreachable
        console.warn(
          "API demo-login unreachable, falling back to direct Supabase auth:",
          apiErr
        );
      }

      // 2. Direct Supabase Auth fallback
      if (!loggedIn) {
        const creds = DEMO_CREDENTIALS[role];
        if (creds) {
          const { error } = await supabase.auth.signInWithPassword({
            email: creds.email,
            password: creds.password,
          });
          if (error) throw error;
        }
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
      keyboardVerticalOffset={Platform.OS === "ios" ? 10 : 0}
      style={styles.container}
    >
      <ScrollView
        contentContainerStyle={[
          styles.scroll,
          {
            paddingTop: Math.max(insets.top + 10, 16),
            paddingBottom: Math.max(insets.bottom + 20, 24),
            paddingHorizontal: isSmallWidth ? 12 : isTablet ? 32 : 18,
            justifyContent: isCompactHeight ? "flex-start" : "center",
          },
        ]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View
          style={[
            styles.card,
            {
              padding: isSmallWidth ? 16 : isTablet ? 28 : 22,
              maxWidth: 440,
              width: "100%",
              alignSelf: "center",
            },
          ]}
        >
          <Text style={[styles.title, isSmallWidth && { fontSize: 20 }]}>
            Campus Recruiting
          </Text>
          <Text
            style={[
              styles.subtitle,
              isSmallWidth && { fontSize: 12, marginBottom: 14 },
            ]}
          >
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

          {/* Google OAuth Button */}
          <TouchableOpacity
            style={[
              styles.googleButton,
              isSmallWidth && { paddingVertical: 11 },
              googleLoading && styles.buttonDisabled,
            ]}
            disabled={googleLoading || loading}
            onPress={handleGoogleLogin}
          >
            {googleLoading ? (
              <ActivityIndicator size="small" color="#EA4335" />
            ) : (
              <>
                <Ionicons
                  name="logo-google"
                  size={isSmallWidth ? 16 : 18}
                  color="#EA4335"
                  style={styles.googleIcon}
                />
                <Text
                  style={[
                    styles.googleButtonText,
                    isSmallWidth && { fontSize: 13 },
                  ]}
                >
                  Continue with Google
                </Text>
              </>
            )}
          </TouchableOpacity>

          <View
            style={[styles.dividerRow, isSmallWidth && { marginVertical: 10 }]}
          >
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>OR CONTINUE WITH EMAIL</Text>
            <View style={styles.dividerLine} />
          </View>

          <Text style={styles.label}>EMAIL ADDRESS</Text>
          <TextInput
            style={[
              styles.input,
              isSmallWidth && { paddingVertical: 10, fontSize: 13 },
            ]}
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
                style={[
                  styles.input,
                  isSmallWidth && { paddingVertical: 10, fontSize: 13 },
                ]}
                secureTextEntry
                value={password}
                onChangeText={setPassword}
                placeholder="••••••••"
                placeholderTextColor="#94a3b8"
              />
            </>
          )}

          <TouchableOpacity
            style={[
              styles.button,
              isSmallWidth && { paddingVertical: 12, marginTop: 14 },
              loading && styles.buttonDisabled,
            ]}
            disabled={loading || googleLoading}
            onPress={handleAuth}
          >
            {loading ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <Text
                style={[styles.buttonText, isSmallWidth && { fontSize: 14 }]}
              >
                {useMagicLink
                  ? "Send Magic Link"
                  : isSignUp
                    ? "Create Account"
                    : "Sign In"}
              </Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.switchButton, isSmallWidth && { marginTop: 10 }]}
            onPress={() => setUseMagicLink(!useMagicLink)}
          >
            <Text style={[styles.switchText, isSmallWidth && { fontSize: 12 }]}>
              {useMagicLink
                ? "Sign in with Password instead"
                : "Sign in with Magic Link"}
            </Text>
          </TouchableOpacity>

          {!useMagicLink && (
            <TouchableOpacity
              style={[styles.switchButton, { marginTop: 8 }]}
              onPress={() => setIsSignUp(!isSignUp)}
            >
              <Text
                style={[styles.switchSubtext, isSmallWidth && { fontSize: 11 }]}
              >
                {isSignUp
                  ? "Already have an account? Sign In"
                  : "Don't have an account? Sign Up"}
              </Text>
            </TouchableOpacity>
          )}

          {/* Quick Demo Access Buttons */}
          <View
            style={[
              styles.demoSection,
              isSmallWidth && { marginTop: 16, paddingTop: 12 },
            ]}
          >
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
                  style={[
                    styles.demoButton,
                    isSmallWidth && { width: "100%", paddingVertical: 8 },
                  ]}
                  disabled={
                    demoRoleLoading !== null || loading || googleLoading
                  }
                  onPress={() => handleDemoLogin(item.role)}
                >
                  {demoRoleLoading === item.role ? (
                    <ActivityIndicator size="small" color="#4f46e5" />
                  ) : (
                    <Text
                      style={[
                        styles.demoButtonText,
                        isSmallWidth && { fontSize: 11 },
                      ]}
                    >
                      {item.label}
                    </Text>
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
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: 20,
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
  googleButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 12,
    paddingVertical: 13,
    marginBottom: 6,
    shadowColor: "#000",
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  googleIcon: {
    marginRight: 10,
  },
  googleButtonText: {
    color: "#1e293b",
    fontSize: 14,
    fontWeight: "600",
  },
  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 14,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: "#e2e8f0",
  },
  dividerText: {
    marginHorizontal: 10,
    fontSize: 10,
    fontWeight: "600",
    color: "#94a3b8",
  },
  label: {
    fontSize: 11,
    fontWeight: "700",
    color: "#475569",
    marginBottom: 5,
    marginTop: 8,
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
    marginTop: 18,
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
    marginTop: 12,
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
    marginTop: 22,
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
