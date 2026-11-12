import AsyncStorage from "@react-native-async-storage/async-storage";
import { createSharedSupabaseClient } from "@recruiting/shared";
import { SupabaseClient } from "@supabase/supabase-js";
import { Platform } from "react-native";

const supabaseUrl =
  process.env.EXPO_PUBLIC_SUPABASE_URL ||
  "https://bsegerbrkbxnosyojmwf.supabase.co";
const supabaseAnonKey =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzZWdlcmJya2J4bm9zeW9qbXdmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTM5ODE5ODQsImV4cCI6MjEwOTU1Nzk4NH0.kmNEXwvifmNltHamteIKuZUUJ2w7Sqip5WnhQFsI4dQ";

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

// Ordered list of candidate backend URLs for auto-discovery and failover
export const CANDIDATE_API_URLS: string[] = [
  // 1. Android emulator loopback alias (highest priority on Android emulator)
  Platform.OS === "android" ? "http://10.0.2.2:8001" : "http://localhost:8001",
  // 2. Wi-Fi LAN IP (highest priority for physical devices on same Wi-Fi)
  "http://192.168.29.133:8001",
  // 3. Configured environment URL
  process.env.EXPO_PUBLIC_API_BASE_URL || "",
  // 4. Standard localhosts
  "http://localhost:8001",
  "http://127.0.0.1:8001",
].filter(Boolean);

let cachedWorkingBaseUrl: string | null = null;

export async function getEffectiveApiBaseUrl(): Promise<string> {
  if (cachedWorkingBaseUrl) return cachedWorkingBaseUrl;
  try {
    const custom = await AsyncStorage.getItem("custom_api_base_url");
    if (custom && custom.trim()) {
      cachedWorkingBaseUrl = custom.trim();
      return cachedWorkingBaseUrl;
    }
  } catch {
    // Ignore storage read error and fallback to candidate list
  }
  return CANDIDATE_API_URLS[0];
}

export function setEffectiveApiBaseUrl(url: string) {
  cachedWorkingBaseUrl = url.trim();
}

export async function saveCustomApiBaseUrl(url: string): Promise<void> {
  const clean = url.trim().replace(/\/+$/, "");
  cachedWorkingBaseUrl = clean;
  await AsyncStorage.setItem("custom_api_base_url", clean);
}

/**
 * Executes an API request with automatic multi-host failover.
 * If the current URL encounters "Network request failed", it immediately
 * retries across alternate candidate URLs (e.g. switching between Emulator 10.0.2.2
 * and Wi-Fi IP 192.168.29.133) and saves the working URL.
 */
export async function withApiFallback<T>(
  fn: (baseUrl: string) => Promise<T>
): Promise<T> {
  const primaryUrl = await getEffectiveApiBaseUrl();
  try {
    const res = await fn(primaryUrl);
    setEffectiveApiBaseUrl(primaryUrl);
    return res;
  } catch (err: any) {
    const isNetworkErr =
      err?.message?.includes("Network request failed") ||
      err?.message?.includes("Failed to fetch") ||
      err?.message?.includes("NetworkError") ||
      err?.message?.includes("connect ECONNREFUSED");

    if (!isNetworkErr) throw err;

    // Iterate through other candidates
    for (const candidate of CANDIDATE_API_URLS) {
      if (candidate === primaryUrl) continue;
      try {
        const res = await fn(candidate);
        setEffectiveApiBaseUrl(candidate);
        await AsyncStorage.setItem("custom_api_base_url", candidate);
        return res;
      } catch {
        // Try next candidate
      }
    }

    throw err;
  }
}

export const API_BASE_URL = CANDIDATE_API_URLS[0];
