import AsyncStorage from "@react-native-async-storage/async-storage";
import { createSharedSupabaseClient } from "@recruiting/shared";
import { SupabaseClient } from "@supabase/supabase-js";

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

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";
