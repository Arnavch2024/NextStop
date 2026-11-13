import { createSharedSupabaseClient } from "@recruiting/shared";
import { SupabaseClient } from "@supabase/supabase-js";

// Production defaults (Supabase project bsegerbrkbxnosyojmwf)
const PRODUCTION_SUPABASE_URL = "https://bsegerbrkbxnosyojmwf.supabase.co";
const PRODUCTION_SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzZWdlcmJya2J4bm9zeW9qbXdmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTM5ODE5ODQsImV4cCI6MjEwOTU1Nzk4NH0.kmNEXwvifmNltHamteIKuZUUJ2w7Sqip5WnhQFsI4dQ";
export const PRODUCTION_RENDER_BACKEND_URL =
  "https://nextstop-backend-1xbe.onrender.com";

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || PRODUCTION_SUPABASE_URL;
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || PRODUCTION_SUPABASE_ANON_KEY;

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
    const timeout = setTimeout(() => controller.abort(), 2500);
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
    // Fallback to production cloud backend
  }

  // 3. Fallback to production Render Cloud backend
  return PRODUCTION_RENDER_BACKEND_URL;
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || PRODUCTION_RENDER_BACKEND_URL;
