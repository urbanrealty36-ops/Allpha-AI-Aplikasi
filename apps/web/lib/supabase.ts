import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let browserClient: SupabaseClient | null | undefined;

export function getBrowserSupabase(): SupabaseClient | null {
  if (typeof window === "undefined") return null;
  if (browserClient !== undefined) return browserClient;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  browserClient = url && publishableKey
    ? createClient(url, publishableKey, {
        auth: {
          autoRefreshToken: true,
          persistSession: true,
          detectSessionInUrl: true,
        },
      })
    : null;
  return browserClient;
}
