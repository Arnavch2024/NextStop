import {
  createClient,
  SupabaseClient,
  SupabaseClientOptions,
} from "@supabase/supabase-js";

/**
 * Creates a configured Supabase client.
 */
export function createSharedSupabaseClient(
  supabaseUrl: string,
  supabaseAnonKey: string,
  options?: SupabaseClientOptions<"public">
): SupabaseClient {
  return createClient(supabaseUrl, supabaseAnonKey, options);
}
