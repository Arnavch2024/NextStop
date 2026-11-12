import { createSharedSupabaseClient } from "@recruiting/shared";
import { SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || "https://placeholder.supabase.co";
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "placeholder-anon-key";

let browserClient: SupabaseClient | null = null;

export function getSupabaseBrowserClient(): SupabaseClient {
  if (!browserClient) {
    browserClient = createSharedSupabaseClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }
  return browserClient;
}

const REGISTRY_CONFIG_URL = `${supabaseUrl}/storage/v1/object/public/app-config/backend_url.json`;

let cachedApiBaseUrl: string | null = null;

export async function getEffectiveApiBaseUrl(): Promise<string> {
  if (cachedApiBaseUrl) return cachedApiBaseUrl;

  // 1. If explicit env var is set, use it
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/+$/, "");
    cachedApiBaseUrl = envUrl;
    return envUrl;
  }

  // 2. Fetch live discovered URL from Supabase Cloud registry
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(REGISTRY_CONFIG_URL, {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(timeout);
    if (res.ok) {
      const data = await res.json();
      if (data?.api_base_url && typeof data.api_base_url === "string") {
        const discovered = data.api_base_url.trim().replace(/\/+$/, "");
        cachedApiBaseUrl = discovered;
        return discovered;
      }
    }
  } catch {
    // Fallback to local
  }

  // 3. Fallback to default port 8001
  return "http://localhost:8001";
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001";
