"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

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
  reason: "mutual_connections";
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
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
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
        apiRequest<{ items: Recommendation[] }>(apiBase, accessToken, "/v1/social/recommendations?limit=12"),
      ]);
      setInterests(interestData.items || []);
      setRecommendations(recommendationData.items || []);
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
      setError("Gunakan 1–80 karakter: huruf kecil, angka, titik, garis bawah, atau tanda hubung.");
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

  async function followRecommendation(item: Recommendation) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiRequest(apiBase, accessToken, "/v1/social/relationships", {
        method: "POST",
        body: JSON.stringify({ target_type: "human", target_id: item.id, edge_type: "follow" }),
      });
      setNotice("Relasi mengikuti " + (item.display_name || item.username || "pengguna") + " tersimpan.");
      setRecommendations((current) => current.filter((candidate) => candidate.id !== item.id));
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
              <input id="social-interest-key" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={80} placeholder="contoh: ai.film atau design" className="min-w-0 rounded-xl border-2 border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900" />
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
                      <p className="truncate text-xs text-slate-500">{item.username ? "@" + item.username + " · " : ""}{item.mutual_followers_count} koneksi bersama</p>
                    </div>
                    <button type="button" disabled={busy} onClick={() => void followRecommendation(item)} className="shrink-0 rounded-full border-2 border-slate-900 bg-sky-100 px-3 py-2 text-xs font-black disabled:opacity-50">Ikuti</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
