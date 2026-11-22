"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getBrowserSupabase } from "@/lib/supabase";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\\/$/, "");

export type AllphaLocale = "id-ID" | "en-US";
type LocaleContextValue = { locale: AllphaLocale; setLocale: (locale: AllphaLocale) => void; t: (key: string) => string };
const messages: Record<string, { id: string; en: string }> = {
  "language.label": { id: "Bahasa", en: "Language" },
  "onboarding.counter": { id: "Slide Sapa", en: "Welcome slide" },
  "onboarding.counterOf": { id: "dari", en: "of" },
  "auth.accountStep": { id: "Akun Human", en: "Human account" },
  "auth.registerTitle": { id: "Registrasi Human Identity", en: "Create your Allpha account" },
  "auth.loginTitle": { id: "Masuk ke Human Identity", en: "Sign in to Allpha" },
  "auth.registerTab": { id: "Daftar", en: "Sign up" },
  "auth.loginTab": { id: "Masuk", en: "Sign in" },
  "auth.name": { id: "Nama Lengkap", en: "Full name" },
  "auth.username": { id: "Username (@handle)", en: "Username (@handle)" },
  "auth.email": { id: "Email", en: "Email" },
  "auth.password": { id: "Password", en: "Password" },
  "auth.bio": { id: "Bio Singkat", en: "Short bio" },
  "auth.interests": { id: "Pilih Minat & Topik Utama", en: "Choose your interests and topics" },
  "auth.back": { id: "Kembali", en: "Back" },
  "auth.submitRegister": { id: "Buat Akun Allpha", en: "Create Allpha account" },
  "auth.submitLogin": { id: "Masuk ke Allpha Universe", en: "Sign in to Allpha Universe" },
  "auth.processing": { id: "Memproses…", en: "Processing…" },
  "auth.forgotPassword": { id: "Lupa password?", en: "Forgot password?" },
};
const LocaleContext = createContext<LocaleContextValue | null>(null);
const STORAGE_KEY = "allpha.locale";

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AllphaLocale>("id-ID");

  useEffect(() => {
    let active = true;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const browserLocale = window.navigator.language.toLowerCase().startsWith("en") ? "en-US" : "id-ID";
    const next: AllphaLocale = stored === "en-US" || stored === "id-ID" ? stored : browserLocale;
    setLocaleState(next);
    document.documentElement.lang = next === "id-ID" ? "id" : "en";

    const supabase = getBrowserSupabase();
    const hydrateProfileLocale = async (accessToken: string) => {
      try {
        const response = await fetch(apiBase + "/v1/me", {
          headers: { Authorization: "Bearer " + accessToken },
          cache: "no-store",
        });
        if (!response.ok) return;
        const payload = await response.json() as { profile?: { locale?: string | null } | null };
        const profileLocale = payload.profile?.locale;
        if (!active || (profileLocale !== "id-ID" && profileLocale !== "en-US")) return;
        setLocaleState(profileLocale);
        window.localStorage.setItem(STORAGE_KEY, profileLocale);
        document.documentElement.lang = profileLocale === "id-ID" ? "id" : "en";
      } catch {
        // Keep the last locally selected language when the profile cannot be loaded.
      }
    };

    if (supabase) {
      void supabase.auth.getSession().then(({ data }) => {
        if (active && data.session?.access_token) void hydrateProfileLocale(data.session.access_token);
      });
      const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
        if (session?.access_token) void hydrateProfileLocale(session.access_token);
      });
      return () => { active = false; subscription.unsubscribe(); };
    }
    return () => { active = false; };
  }, []);

  const setLocale = useCallback((next: AllphaLocale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next === "id-ID" ? "id" : "en";
    window.dispatchEvent(new CustomEvent("allpha:locale-change", { detail: next }));
  }, []);

  const t = useCallback((key: string) => messages[key]?.[locale === "id-ID" ? "id" : "en"] ?? key, [locale]);
  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used inside LocaleProvider");
  return context;
}
