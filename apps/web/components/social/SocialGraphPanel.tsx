"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

type InterestGraphSignal = { interest_key: string; signal_type: "passion" | "habit"; strength: number; signal_source: string; updated_at: string };
type CatalogInterest = { interest_key: string; label: string; category: string; sensitivity: "standard" | "sensitive" };

type Interest = {
  interest_key: string;
  preference: "interested" | "not_interested";
  created_at?: string;
  updated_at?: string;
};

type Recommendation = {
  id: string;
  username: string | null;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  mutual_followers_count: number;
  shared_interests_count: number;
  recommendation_score: number;
  reason: "mutual_connections" | "shared_interests" | "mutual_connections_and_shared_interests";
};

type AgentRecommendation = {
  id: string;
  handle: string;
  display_name: string | null;
  avatar_url: string | null;
  description: string | null;
  mutual_followers_count: number;
  shared_interests_count: number;
  recommendation_score: number;
  reason: "owned_by_mutual_connection" | "owned_by_mutual_connection_and_shared_interests";
};

type Props = { apiBase: string; accessToken: string };

async function apiRequest<T>(apiBase: string, accessToken: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(apiBase + path, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: "Bearer " + accessToken,
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.detail?.message || payload?.error?.message || "Permintaan Social Graph gagal.");
  return payload as T;
}

function labelForInterest(key: string): string {
  return key.replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function SocialGraphPanel({ apiBase, accessToken }: Props) {
  const [interests, setInterests] = useState<Interest[]>([]);
  const [catalog, setCatalog] = useState<CatalogInterest[]>([]);
  const [interestSignals, setInterestSignals] = useState<InterestGraphSignal[]>([]);
  const [passionKey, setPassionKey] = useState("");
  const [habitKey, setHabitKey] = useState("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [agentRecommendations, setAgentRecommendations] = useState<AgentRecommendation[]>([]);
  const [agentRecommendationError, setAgentRecommendationError] = useState("");
  const [draft, setDraft] = useState("");
  const [preference, setPreference] = useState<Interest["preference"]>("interested");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [interestData, recommendationData] = await Promise.all([
        apiRequest<{ items: Interest[] }>(apiBase, accessToken, "/v1/me/interests"),
        apiRequest<{ items: Recommendation[] }>(apiBase, accessToken, "/v1/social/recommendations?node_type=human&limit=12"),
      ]);
      setInterests(interestData.items || []);
      setRecommendations(recommendationData.items || []);
      try {
        const catalogData = await apiRequest<{ items: CatalogInterest[] }>(apiBase, accessToken, "/v1/interests/catalog");
        setCatalog(Array.isArray(catalogData.items) ? catalogData.items : []);
      } catch {
        setCatalog([]);
      }
      try {
        const signalData = await apiRequest<{ items: InterestGraphSignal[] }>(apiBase, accessToken, "/v1/me/interest-signals");
        setInterestSignals(signalData.items || []);
      } catch {
        setInterestSignals([]);
      }
      try {
        const agentData = await apiRequest<{ items: AgentRecommendation[] }>(apiBase, accessToken, "/v1/social/recommendations?node_type=agent&limit=12");
        setAgentRecommendations(agentData.items || []);
        setAgentRecommendationError("");
      } catch (cause) {
        setAgentRecommendations([]);
        setAgentRecommendationError(cause instanceof Error ? cause.message : "Rekomendasi AI Agent belum tersedia.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Social Graph belum dapat dimuat.");
    } finally {
      setLoading(false);
    }
  }, [apiBase, accessToken]);

  useEffect(() => { void load(); }, [load]);

  async function saveInterest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = draft.trim().toLowerCase();
    if (!/^[a-z0-9][a-z0-9._-]{0,79}$/.test(key)) {
      setError("Pilih minat dari taksonomi resmi Allpha.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest(apiBase, accessToken, "/v1/me/interests", {
        method: "PUT", body: JSON.stringify({ interest_key: key, preference }),
      });
      setDraft("");
      setNotice("Preferensi minat tersimpan.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preferensi minat gagal disimpan.");
    } finally {
      setBusy(false);
    }
  }

  async function removeInterest(key: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest(apiBase, accessToken, "/v1/me/interests/" + encodeURIComponent(key), { method: "DELETE" });
      setNotice("Preferensi minat dihapus.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Preferensi minat gagal dihapus.");
    } finally {
      setBusy(false);
    }
  }

  async function saveInterestSignal(signalType: "passion" | "habit", key: string) {
    const interest = key.trim().toLowerCase();
    if (!interest) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest(apiBase, accessToken, "/v1/me/interest-signals", {
        method: "PUT",
        body: JSON.stringify({
          interest_key: interest, signal_type: signalType, strength: 1,
          signal_source: "user_selected", consent_version: "interest-graph-v1",
        }),
      });
      if (signalType === "passion") setPassionKey(""); else setHabitKey("");
      setNotice(signalType === "passion" ? "Passion Graph diperbarui." : "Habit Graph diperbarui.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sinyal Graph gagal disimpan."); }
    finally { setBusy(false); }
  }

  async function removeInterestSignal(signal: InterestGraphSignal) {
    setBusy(true); setError(""); setNotice("");
    try {
      await apiRequest(apiBase, accessToken, "/v1/me/interest-signals/" + signal.signal_type + "/" + encodeURIComponent(signal.interest_key), { method: "DELETE" });
      setNotice("Sinyal " + signal.signal_type + " dihapus.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sinyal Graph gagal dihapus."); }
    finally { setBusy(false); }
  }

  async function followRecommendation(item: Recommendation | AgentRecommendation, targetType: "human" | "agent") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest(apiBase, accessToken, "/v1/social/relationships", {
        method: "POST",
        body: JSON.stringify({ target_type: targetType, target_id: item.id, edge_type: "follow" }),
      });
      const identityLabel = item.display_name || ("username" in item ? item.username : item.handle) || "identitas";
      setNotice("Relasi mengikuti " + identityLabel + " tersimpan.");
      if (targetType === "human") setRecommendations((current) => current.filter((candidate) => candidate.id !== item.id));
      else setAgentRecommendations((current) => current.filter((candidate) => candidate.id !== item.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Relasi gagal disimpan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="social-graph-heading" className="mx-auto my-6 w-full max-w-6xl px-4 sm:px-6">
      <div className="rounded-3xl border-2 border-slate-900 bg-white p-5 shadow-[3px_3px_0px_#0f172a] sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-indigo-600">Social Graph</p>
            <h2 id="social-graph-heading" className="mt-1 text-xl font-black text-slate-950">Minat & rekomendasi koneksi</h2>
            <p className="mt-1 text-sm text-slate-600">Kelola minat Anda dan temukan profil publik berdasarkan koneksi bersama yang dapat ditemukan.</p>
          </div>
          <button type="button" onClick={() => void load()} disabled={loading || busy} className="rounded-full border-2 border-slate-900 px-4 py-2 text-xs font-black disabled:opacity-50">Muat ulang</button>
        </div>
        {error && <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
        {notice && <p role="status" aria-live="polite" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-base font-black text-slate-950">Interest Graph</h3>
            <p className="mt-1 text-xs text-slate-500">Preferensi minat hanya dikelola pada akun Anda.</p>
            <form onSubmit={saveInterest} className="mt-3 grid gap-2 sm:grid-cols-[1fr_170px_auto]">
              <label className="sr-only" htmlFor="social-interest-key">Kunci minat</label>
              <select id="social-interest-key" value={draft} onChange={(event) => setDraft(event.target.value)} className="min-w-0 rounded-xl border-2 border-slate-300 px-3 py-2 text-sm">
                <option value="">Pilih minat dari taksonomi Allpha</option>
                {catalog.map(item => <option key={item.interest_key} value={item.interest_key}>{item.label + (item.sensitivity === "sensitive" ? " · pilihan eksplisit" : "")} · {item.category}</option>)}
              </select>
              <label className="sr-only" htmlFor="social-interest-preference">Preferensi</label>
              <select id="social-interest-preference" value={preference} onChange={(event) => setPreference(event.target.value as Interest["preference"])} className="rounded-xl border-2 border-slate-300 px-3 py-2 text-sm">
                <option value="interested">Tertarik</option>
                <option value="not_interested">Tidak tertarik</option>
              </select>
              <button type="submit" disabled={busy || loading || !draft.trim()} className="rounded-xl border-2 border-slate-900 bg-slate-900 px-4 py-2 text-sm font-black text-white disabled:opacity-50">Simpan</button>
            </form>
            {loading ? <p className="mt-4 text-sm text-slate-500">Memuat minat…</p> : interests.length === 0 ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Belum ada preferensi minat tersimpan.</p> : (
              <ul className="mt-4 flex flex-wrap gap-2">
                {interests.map((item) => (
                  <li key={item.interest_key} className="flex items-center gap-2 rounded-full border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-800">
                    <span>{labelForInterest(item.interest_key)}</span>
                    <span className="text-slate-500">{item.preference === "interested" ? "· Tertarik" : "· Tidak tertarik"}</span>
                    <button type="button" aria-label={"Hapus minat " + item.interest_key} disabled={busy} onClick={() => void removeInterest(item.interest_key)} className="font-black text-rose-700 disabled:opacity-50">×</button>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-5 grid gap-3 border-t border-slate-200 pt-4">
              <div>
                <h3 className="text-sm font-black text-slate-950">Passion Graph</h3>
                <p className="text-xs text-slate-500">Minat mendalam yang Anda pilih secara eksplisit; tidak disimpulkan dari atribut sensitif.</p>
                <div className="mt-2 flex gap-2">
                  <select aria-label="Pilih Passion Graph" value={passionKey} onChange={event => setPassionKey(event.target.value)} className="min-w-0 flex-1 rounded-xl border-2 border-slate-300 px-3 py-2 text-sm"><option value="">Pilih topik dari taksonomi</option>{catalog.map(item => <option key={item.interest_key} value={item.interest_key}>{item.label + (item.sensitivity === "sensitive" ? " · pilihan eksplisit" : "")}</option>)}</select>
                  <button type="button" disabled={busy || !passionKey.trim()} onClick={() => void saveInterestSignal("passion", passionKey)} className="rounded-xl border-2 border-slate-900 px-3 py-2 text-xs font-black disabled:opacity-50">Simpan</button>
                </div>
              </div>
              <div>
                <h3 className="text-sm font-black text-slate-950">Habit Graph</h3>
                <p className="text-xs text-slate-500">Pola yang Anda pilih sendiri. Sinyal observasi hanya diizinkan saat personalisasi aktif.</p>
                <div className="mt-2 flex gap-2">
                  <select aria-label="Pilih Habit Graph" value={habitKey} onChange={event => setHabitKey(event.target.value)} className="min-w-0 flex-1 rounded-xl border-2 border-slate-300 px-3 py-2 text-sm"><option value="">Pilih topik dari taksonomi</option>{catalog.map(item => <option key={item.interest_key} value={item.interest_key}>{item.label + (item.sensitivity === "sensitive" ? " · pilihan eksplisit" : "")}</option>)}</select>
                  <button type="button" disabled={busy || !habitKey.trim()} onClick={() => void saveInterestSignal("habit", habitKey)} className="rounded-xl border-2 border-slate-900 px-3 py-2 text-xs font-black disabled:opacity-50">Simpan</button>
                </div>
              </div>
              {interestSignals.map(signal => <div key={signal.signal_type + ":" + signal.interest_key} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-3">
                <div><p className="text-sm font-bold text-slate-900">{signal.signal_type === "passion" ? "Passion" : "Habit"} · {labelForInterest(signal.interest_key)}</p><p className="text-xs text-slate-500">Sumber: {signal.signal_source} · Strength {signal.strength}</p></div>
                <button type="button" disabled={busy} onClick={() => void removeInterestSignal(signal)} className="rounded-full border border-rose-300 px-3 py-1 text-xs font-bold text-rose-700 disabled:opacity-50">Hapus</button>
              </div>)}
            </div>
          </div>
          <div>
            <h3 className="text-base font-black text-slate-950">Rekomendasi Human</h3>
            <p className="mt-1 text-xs text-slate-500">Hanya profil publik dan discoverable; koneksi bersama tidak menampilkan identitas sumber.</p>
            {loading ? <p className="mt-4 text-sm text-slate-500">Mencari koneksi…</p> : recommendations.length === 0 ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Belum ada rekomendasi koneksi yang memenuhi preferensi privasi.</p> : (
              <ul className="mt-3 space-y-2">
                {recommendations.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-slate-900">{item.display_name || item.username || "Pengguna"}</p>
                      <p className="truncate text-xs text-slate-500">{item.username ? "@" + item.username + " · " : ""}{item.mutual_followers_count} koneksi bersama{item.shared_interests_count > 0 ? " · " + item.shared_interests_count + " minat sama" : ""}</p>
                    </div>
                    <button type="button" disabled={busy} onClick={() => void followRecommendation(item, "human")} className="shrink-0 rounded-full border-2 border-slate-900 bg-sky-100 px-3 py-2 text-xs font-black disabled:opacity-50">Ikuti</button>
                  </li>
                ))}
              </ul>
            )}
          <div className="mt-6">
            <h3 className="text-base font-black text-slate-950">Rekomendasi AI Agent</h3>
            <p className="mt-1 text-xs text-slate-500">Agent publik dengan pemilik dari koneksi bersama yang dapat ditemukan.</p>
            {agentRecommendationError && <p role="alert" className="mt-3 text-sm text-rose-700">{agentRecommendationError}</p>}
            {loading ? <p className="mt-4 text-sm text-slate-500">Mencari AI Agent…</p> : agentRecommendations.length === 0 ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Belum ada AI Agent publik yang memenuhi pengaturan privasi.</p> : (
              <ul className="mt-3 space-y-2">
                {agentRecommendations.map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-slate-900">{item.display_name || item.handle}</p>
                      <p className="truncate text-xs text-slate-500">@{item.handle} · {item.mutual_followers_count} koneksi pemilik{item.shared_interests_count > 0 ? " · " + item.shared_interests_count + " minat sama" : ""}</p>
                    </div>
                    <button type="button" disabled={busy} onClick={() => void followRecommendation(item, "agent")} className="shrink-0 rounded-full border-2 border-slate-900 bg-violet-100 px-3 py-2 text-xs font-black disabled:opacity-50">Ikuti Agent</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          </div>
        </div>
      </div>
    </section>
  );
}
