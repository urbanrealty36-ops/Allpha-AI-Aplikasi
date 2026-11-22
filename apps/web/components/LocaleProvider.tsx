"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type AllphaLocale = "id-ID" | "en-US";
type LocaleContextValue = { locale: AllphaLocale; setLocale: (locale: AllphaLocale) => void };
const LocaleContext = createContext<LocaleContextValue | null>(null);
const STORAGE_KEY = "allpha.locale";

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<AllphaLocale>("id-ID");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    const browserLocale = window.navigator.language.toLowerCase().startsWith("en") ? "en-US" : "id-ID";
    const next: AllphaLocale = stored === "en-US" || stored === "id-ID" ? stored : browserLocale;
    setLocaleState(next);
    document.documentElement.lang = next === "id-ID" ? "id" : "en";
  }, []);

  const setLocale = useCallback((next: AllphaLocale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next === "id-ID" ? "id" : "en";
    window.dispatchEvent(new CustomEvent("allpha:locale-change", { detail: next }));
  }, []);

  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used inside LocaleProvider");
  return context;
}
