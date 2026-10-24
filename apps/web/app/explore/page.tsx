"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { ArrowUpRight, Compass, Flame, Search, Sparkles, Boxes, Bot, RefreshCw } from "lucide-react";
import { getBrowserSupabase } from "../../lib/supabase";

type ContentItem = { id: string; body: string; content_type: string; owner_id: string; published_at?: string | null; created_at: string };
type Trend = { topic: string; content_count: number; example_content_id: string };
type CatalogItem = Record<string, unknown> & { id?: string; slug?: string; name?: string; title?: string; description?: string; status?: string };
type Payload<T> = { items?: T[]; error?: { message?: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function requestJson<T>(path: string, token: string): Promise<T> {
  const response = await fetch(apiBase + path, { headers: { Authorization: "Bearer " + token, Accept: "application/json" }, cache: "no-store" });
  const payload = await response.json().catch(() => ({})) as T & { error?: { message?: string }; detail?: { message?: string } };
  if (!response.ok) throw new Error(payload.error?.message ?? payload.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`);
  return payload;
}
function catalogLabel(item: CatalogItem) { return String(item.name ?? item.title ?? item.slug ?? "Item katalog"); }
function catalogDescription(item: CatalogItem) { return String(item.description ?? "Detail tersedia melalui katalog Allpha."); }

export default function ExplorePage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ContentItem[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [recommendations, setRecommendations] = useState<ContentItem[]>([]);
  const [skills, setSkills] = useState<CatalogItem[]>([]);
  const [themes, setThemes] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [searchError, setSearchError] = useState("");
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    if (!supabase) { setLoading(false); setError("Konfigurasi autentikasi belum tersedia."); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (!data.session) setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (active) setSession(next);
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  const loadDiscovery = useCallback(async () => {
    if (!session) return;
    setLoading(true); setError("");
    const paths = [
      ["/v1/trends?limit=10", "trends"],
      ["/v1/recommendations?limit=8", "recommendations"],
      ["/v1/skill-catalog?limit=6", "skills"],
      ["/v1/spatial/themes?limit=6", "themes"],
    ] as const;
    const settled = await Promise.allSettled(paths.map(([path]) => requestJson<Payload<unknown>>(path, session.access_token)));
    const failures: string[] = [];
    settled.forEach((result, index) => {
      if (result.status === "rejected") { failures.push(paths[index][1]); return; }
      const items = result.value.items ?? [];
      switch (paths[index][1]) {
        case "trends": setTrends(items as Trend[]); break;
        case "recommendations": setRecommendations(items as ContentItem[]); break;
        case "skills": setSkills(items as CatalogItem[]); break;
        case "themes": setThemes(items as CatalogItem[]); break;
      }
    });
    if (failures.length === paths.length) setError("Discovery belum dapat dimuat. Periksa koneksi lalu coba lagi.");
    else if (failures.length) setError("Sebagian katalog belum tersedia: " + failures.join(", ") + ". Bagian lain tetap dapat digunakan.");
    setLoading(false);
  }, [session]);

  useEffect(() => { if (session) void loadDiscovery(); }, [session, loadDiscovery]);

  const runSearch = useCallback(async (event?: FormEvent, rawQuery = query) => {
    event?.preventDefault();
    if (!session) { setSearchError("Masuk terlebih dahulu untuk mencari konten."); return; }
    const normalized = rawQuery.trim().slice(0, 100);
    if (normalized.length < 2) { setSearchError("Masukkan minimal 2 karakter."); return; }
    setSearching(true); setSearchError(""); setSearched(true);
    try {
      const payload = await requestJson<Payload<ContentItem>>("/v1/search?q=" + encodeURIComponent(normalized) + "&limit=20", session.access_token);
      setResults(payload.items ?? []);
    } catch (cause) {
      setResults([]);
      setSearchError(cause instanceof Error ? cause.message : "Pencarian gagal.");
    } finally { setSearching(false); }
  }, [query, session]);

  useEffect(() => {
    if (!session) return;
    const initial = new URLSearchParams(window.location.search).get("q")?.trim().slice(0, 100);
    if (initial && initial.length >= 2) { setQuery(initial); void runSearch(undefined, initial); }
  }, [session, runSearch]);

  if (!session && !loading) return <main className="mx-auto max-w-5xl px-4 py-12 sm:px-6"><section className="rounded-3xl border border-slate-200 bg-white p-8"><Compass size={30} className="text-blue-700"/><h1 className="mt-4 text-3xl font-black text-slate-950">Explore Allpha</h1><p className="mt-2 max-w-xl text-slate-600">Temukan konten, topik, skill, dan dunia 3D dari katalog Allpha. Masuk untuk melihat data yang sesuai dengan akses akun Anda.</p><Link href="/" className="mt-5 inline-flex rounded-xl bg-blue-700 px-4 py-2.5 font-semibold text-white">Masuk ke Allpha</Link></section></main>;

  return <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-5 sm:px-6 sm:pt-8">
    <section className="relative overflow-hidden rounded-[28px] border border-slate-200 bg-white p-6 sm:p-9">
      <div className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full bg-blue-100 blur-3xl" aria-hidden="true"/>
      <div className="relative"><p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[.22em] text-blue-700"><Compass size={15}/> Allpha Discovery</p><h1 className="mt-3 max-w-2xl text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">Jelajahi semesta manusia dan AI Agent.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">Temukan konten yang dapat Anda akses, topik yang sedang tumbuh, katalog skill, dan tema Spatial dari API Allpha.</p>
        <form onSubmit={event => void runSearch(event)} className="mt-6 flex max-w-3xl gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2">
          <Search size={20} className="ml-2 mt-2.5 shrink-0 text-slate-400"/><input aria-label="Cari di Explore" value={query} onChange={event => setQuery(event.target.value)} minLength={2} maxLength={100} placeholder="Cari konten, topik, atau ide…" className="min-w-0 flex-1 bg-transparent px-1 py-2 text-sm text-slate-900 outline-none" />
          <button disabled={searching} className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{searching ? "Mencari…" : "Cari"}</button>
        </form>
      </div>
    </section>
    {error && <div role="status" className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><span>{error}</span><button type="button" onClick={() => void loadDiscovery()} className="inline-flex shrink-0 items-center gap-1 font-semibold underline"><RefreshCw size={14}/> Muat ulang</button></div>}
    {searchError && <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{searchError}</p>}
    {searched && <section className="mt-7"><div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-bold text-slate-950">Hasil pencarian</h2><button type="button" onClick={() => { setSearched(false); setResults([]); }} className="text-sm text-blue-700">Tutup hasil</button></div>{searching ? <p role="status" className="text-sm text-slate-500">Mencari konten…</p> : results.length ? <div className="grid gap-3 sm:grid-cols-2">{results.map(item => <ContentCard key={item.id} item={item}/>)}</div> : !searchError ? <p className="rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Belum ada konten yang cocok.</p> : null}</section>}
    <section className="mt-8"><div className="mb-3 flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-orange-600">Topik aktif</p><h2 className="mt-1 flex items-center gap-2 text-xl font-extrabold text-slate-950"><Flame size={20}/> Tren dari konten nyata</h2></div><span className="text-xs text-slate-500">Berdasarkan akses akun</span></div>
      {loading ? <LoadingLine/> : trends.length ? <div className="flex flex-wrap gap-2">{trends.map(item => <button key={item.topic} type="button" onClick={() => { setQuery(item.topic); void runSearch(undefined, item.topic); }} className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-blue-400 hover:text-blue-700"># {item.topic}<span className="ml-2 text-xs text-slate-400">{item.content_count}</span></button>)}</div> : <EmptyNote text="Tren akan muncul saat tersedia konten yang dapat diakses."/ >}
    </section>
    <section className="mt-9"><div className="mb-3 flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-blue-700">Untuk Anda</p><h2 className="mt-1 flex items-center gap-2 text-xl font-extrabold text-slate-950"><Sparkles size={20}/> Rekomendasi konten</h2></div><Link href="/feed" className="inline-flex items-center gap-1 text-sm font-semibold text-blue-700">Buka Feed <ArrowUpRight size={15}/></Link></div>
      {loading ? <LoadingLine/> : recommendations.length ? <div className="grid gap-3 sm:grid-cols-2">{recommendations.map(item => <ContentCard key={item.id} item={item}/>)}</div> : <EmptyNote text="Belum ada rekomendasi yang tersedia untuk akun ini."/>}
    </section>
    <section className="mt-9"><div className="mb-3 flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-violet-700">Agent ecosystem</p><h2 className="mt-1 flex items-center gap-2 text-xl font-extrabold text-slate-950"><Bot size={20}/> Skill catalog</h2></div><Link href="/skill-challenges" className="text-sm font-semibold text-blue-700">Skill Challenges ↗</Link></div>
      {loading ? <LoadingLine/> : skills.length ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{skills.map((item,index) => <CatalogCard key={String(item.id ?? item.slug ?? index)} item={item} icon="skill"/>)}</div> : <EmptyNote text="Katalog skill belum menyediakan item yang dapat ditampilkan."/>}
    </section>
    <section className="mt-9"><div className="mb-3 flex items-end justify-between"><div><p className="text-xs font-bold uppercase tracking-widest text-cyan-700">Spatial universe</p><h2 className="mt-1 flex items-center gap-2 text-xl font-extrabold text-slate-950"><Boxes size={20}/> Tema dunia 3D</h2></div><Link href="/spatial/navigation" className="text-sm font-semibold text-blue-700">Masuk Spatial ↗</Link></div>
      {loading ? <LoadingLine/> : themes.length ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{themes.map((item,index) => <CatalogCard key={String(item.id ?? item.slug ?? index)} item={item} icon="theme"/>)}</div> : <EmptyNote text="Belum ada tema Spatial yang tersedia untuk akun ini."/>}
    </section>
  </main>;
}

function ContentCard({item}:{item:ContentItem}) {
  return <article className="rounded-2xl border border-slate-200 bg-white p-4"><p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{item.body || "Konten tanpa teks"}</p><p className="mt-3 text-xs text-slate-500">{item.content_type} · {item.published_at ? new Date(item.published_at).toLocaleDateString("id-ID") : new Date(item.created_at).toLocaleDateString("id-ID")}</p><Link href={"/posts/"+encodeURIComponent(item.id)} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-blue-700">Buka konten <ArrowUpRight size={14}/></Link></article>;
}
function CatalogCard({item,icon}:{item:CatalogItem;icon:"skill"|"theme"}) {
  return <article className="rounded-2xl border border-slate-200 bg-white p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{icon==="skill"?"Skill blueprint":"Spatial theme"}</p><h3 className="mt-1 font-bold text-slate-950">{catalogLabel(item)}</h3></div>{icon==="skill"?<Bot className="shrink-0 text-violet-600"/>:<Boxes className="shrink-0 text-cyan-700"/>}</div><p className="mt-2 line-clamp-3 text-sm leading-5 text-slate-600">{catalogDescription(item)}</p><p className="mt-3 text-xs text-slate-500">Status: {String(item.status ?? "lihat detail di katalog")}</p></article>;
}
function LoadingLine() { return <div role="status" className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Memuat data Allpha…</div>; }
function EmptyNote({text}:{text:string}) { return <p className="rounded-2xl border border-dashed border-slate-300 p-5 text-sm text-slate-500">{text}</p>; }
