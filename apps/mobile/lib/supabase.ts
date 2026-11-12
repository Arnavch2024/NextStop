import AsyncStorage from "@react-native-async-storage/async-storage";
import { createSharedSupabaseClient } from "@recruiting/shared";
import { SupabaseClient } from "@supabase/supabase-js";
import { Platform } from "react-native";

const supabaseUrl =
  process.env.EXPO_PUBLIC_SUPABASE_URL || "https://placeholder.supabase.co";
const supabaseAnonKey =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || "placeholder-anon-key";

let mobileClient: SupabaseClient | null = null;

export function getMobileSupabaseClient(): SupabaseClient {
  if (!mobileClient) {
    mobileClient = createSharedSupabaseClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        storage: AsyncStorage,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    });
  }
  return mobileClient;
}

function resolveApiBaseUrl(): string {
  const envUrl =
    process.env.EXPO_PUBLIC_API_BASE_URL || "http://192.168.29.133:8001";
  // On Android emulator, localhost points to the emulator itself.
  // 10.0.2.2 points to the host development machine's localhost.
  if (Platform.OS === "android" && envUrl.includes("localhost")) {
    return envUrl.replace("localhost", "10.0.2.2");
  }
  return envUrl;
}

export const API_BASE_URL = resolveApiBaseUrl();
