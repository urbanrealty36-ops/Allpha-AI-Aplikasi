"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bot, Box, Search, RefreshCw, LoaderCircle, ArrowUpRight, ShieldCheck, Store } from "lucide-react";

type Skill = { id?: string; slug?: string; name?: string; title?: string; description?: string; category?: string; status?: string };
type Theme = { theme_key: string; display_name: string; description?: string; active_version?: number; status?: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
async function fetchPayload<T>(path: string): Promise<T> {
  const response = await fetch(apiBase + path, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!response.ok) {
    let message = `Permintaan gagal (HTTP ${response.status}).`;
    try { const data = await response.json(); message = data?.error?.message ?? data?.detail?.message ?? message; } catch {}
    throw new Error(message);
  }
  return response.json();
}

export default function MarketplacePage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "agents" | "themes">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    const [skillResult, themeResult] = await Promise.allSettled([
      fetchPayload<{ items?: Skill[] }>("/v1/skill-catalog?limit=50"),
      fetchPayload<{ items?: Theme[] }>("/v1/spatial/themes?limit=50"),
    ]);
    if (skillResult.status === "fulfilled") setSkills(skillResult.value.items ?? []);
    if (themeResult.status === "fulfilled") setThemes(themeResult.value.items ?? []);
    const errors = [skillResult, themeResult].filter((result): result is PromiseRejectedResult => result.status === "rejected");
    if (errors.length === 2) setError("Katalog Agent dan Theme tidak dapat dimuat. Periksa koneksi API lalu coba lagi.");
    else if (errors.length === 1) setError("Sebagian katalog tidak tersedia saat ini; hasil dari sumber yang berhasil tetap ditampilkan.");
    setLoading(false);
  }, []);
  useEffect(() => { void load(); }, [load]);

  const visibleSkills = useMemo(() => skills.filter(item => (item.name ?? item.title ?? item.slug ?? "").toLowerCase().includes(query.toLowerCase()) || (item.description ?? "").toLowerCase().includes(query.toLowerCase())), [skills, query]);
  const visibleThemes = useMemo(() => themes.filter(item => (item.display_name + " " + item.theme_key + " " + (item.description ?? "")).toLowerCase().includes(query.toLowerCase())), [themes, query]);
  const showSkills = filter !== "themes";
  const showThemes = filter !== "agents";

  return <main className="mx-auto w-full max-w-5xl px-4 pb-28 pt-5 sm:px-6 sm:pt-8">
    <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
      <div className="relative overflow-hidden bg-slate-950 px-5 py-7 text-white sm:px-8 sm:py-9"><div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(37,99,235,.35),transparent_55%)]" aria-hidden="true"/><div className="relative flex items-start gap-4"><div className="grid size-12 shrink-0 place-items-center rounded-2xl border border-white/15 bg-white/10"><Store size={24}/></div><div><p className="text-xs font-bold uppercase tracking-[0.22em] text-blue-300">DISCOVER · ALLPHA UNIVERSE</p><h1 className="mt-2 text-3xl font-black tracking-tight">Marketplace</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">Jelajahi blueprint AI Agent dan Theme 3D yang benar-benar tersedia pada katalog kanonis Allpha.</p></div></div></div>
      <div className="p-4 sm:p-6">
        <label className="relative block"><Search size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"/><span className="sr-only">Cari katalog</span><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Cari AI Agent atau Theme 3D…" className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-10 pr-4 text-sm text-slate-900 outline-none focus:border-blue-500 focus:bg-white"/></label>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1" role="group" aria-label="Filter katalog">{([{id:"all",label:"Semua"},{id:"agents",label:"AI Agent"},{id:"themes",label:"Theme 3D"}] as const).map(tab=><button key={tab.id} onClick={()=>setFilter(tab.id)} aria-pressed={filter===tab.id} className={`shrink-0 rounded-full border px-4 py-2 text-xs font-semibold ${filter===tab.id?"border-slate-950 bg-slate-950 text-white":"border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>{tab.label}</button>)}</div>
      </div>
    </section>
    {error && <div role="alert" className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><span>{error}</span><button onClick={()=>void load()} className="inline-flex shrink-0 items-center gap-1 font-semibold underline"><RefreshCw size={14}/> Muat ulang</button></div>}
    {loading && <div className="mt-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600"><LoaderCircle size={18} className="animate-spin"/> Memuat katalog nyata dari API…</div>}
    {!loading && showSkills && <section className="mt-7"><div className="mb-3 flex items-end justify-between"><div><h2 className="text-lg font-bold text-slate-950">AI Agent & Skill Blueprint</h2><p className="mt-1 text-xs text-slate-500">Metadata katalog; tidak otomatis memberi izin eksekusi Agent.</p></div><span className="text-xs text-slate-500">{visibleSkills.length} item</span></div>
      {visibleSkills.length===0?<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-7 text-center text-sm text-slate-500">Tidak ada blueprint yang cocok pada katalog saat ini.</div>:<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{visibleSkills.map((item,index)=><article key={item.id ?? item.slug ?? `${item.name}-${index}`} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div className="grid size-10 place-items-center rounded-xl bg-blue-50 text-blue-700"><Bot size={20}/></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase text-slate-600">{item.category ?? "Agent"}</span></div><h3 className="mt-4 font-bold text-slate-950">{item.name ?? item.title ?? item.slug ?? "Agent Blueprint"}</h3><p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{item.description ?? "Deskripsi belum tersedia pada katalog API."}</p><div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3"><span className="text-xs text-slate-500">{item.status ?? "Blueprint"}</span><Link href="/agents" className="inline-flex items-center gap-1 text-xs font-bold text-blue-700 hover:underline">Lihat Agent <ArrowUpRight size={13}/></Link></div></article>)}</div>}</section>}
    {!loading && showThemes && <section className="mt-8"><div className="mb-3 flex items-end justify-between"><div><h2 className="text-lg font-bold text-slate-950">Theme 3D Terpublikasi</h2><p className="mt-1 text-xs text-slate-500">Hanya Theme dengan versi aktif yang dipublikasikan backend.</p></div><span className="text-xs text-slate-500">{visibleThemes.length} item</span></div>
      {visibleThemes.length===0?<div className="rounded-2xl border border-dashed border-slate-300 bg-white p-7 text-center"><Box className="mx-auto text-slate-400" size={25}/><p className="mt-3 text-sm font-semibold text-slate-800">Belum ada Theme publik yang cocok</p><p className="mt-1 text-xs text-slate-500">Katalog tetap kosong sampai proses validasi dan publikasi resmi selesai.</p></div>:<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{visibleThemes.map(theme=><article key={theme.theme_key} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="grid aspect-[16/7] place-items-center bg-[radial-gradient(ellipse_at_top,rgba(37,99,235,.25),transparent_65%),linear-gradient(135deg,#020617,#1e293b)] text-blue-200"><Box size={34}/></div><div className="p-4"><h3 className="font-bold text-slate-950">{theme.display_name}</h3><p className="mt-1 text-xs text-slate-500">{theme.description ?? theme.theme_key}</p><div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3"><span className="inline-flex items-center gap-1.5 text-xs text-slate-500"><ShieldCheck size={13}/> Versi {theme.active_version ?? "—"}</span><Link href="/spatial/navigation" className="inline-flex items-center gap-1 text-xs font-bold text-blue-700 hover:underline">Buka Spatial <ArrowUpRight size={13}/></Link></div></div></article>)}</div>}</section>}
    <p className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-600">Pembelian, harga, order, subscription, dan settlement belum ditawarkan oleh halaman ini: kontrak commerce dan ledger untuk transaksi marketplace belum tersedia pada backend yang diaudit. Tidak ada harga atau tombol beli demo.</p>
  </main>;
}
