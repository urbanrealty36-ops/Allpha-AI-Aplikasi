"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { Film, Play, RefreshCw, Video, AudioLines, Plus, LoaderCircle, ShieldCheck, ArrowUpRight } from "lucide-react";
import { getBrowserSupabase } from "../../lib/supabase";

type Media = { id: string; filename: string; media_type: string; size_bytes?: number; status?: string; storage_path?: string };
type Content = { id: string; body: string; content_type: string; status: string; moderation_status?: string; created_at: string; updated_at: string; published_at?: string | null; media?: Media[] };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function errorMessage(response: Response) {
  try { const data = await response.json(); return data?.error?.message ?? data?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function CinemaPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [items, setItems] = useState<Content[]>([]);
  const [filter, setFilter] = useState<"all" | "video" | "audio">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [previewId, setPreviewId] = useState("");
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});

  const request = useCallback(async (path: string) => {
    if (!session) throw new Error("Masuk terlebih dahulu untuk membuka pustaka Cinema.");
    const response = await fetch(apiBase + path, { headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json();
  }, [session]);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true); setError("");
    try { const payload = await request("/v1/content/mine?limit=100") as { items?: Content[] }; setItems(payload.items ?? []); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pustaka tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [request, session]);

  useEffect(() => {
    if (!supabase) { setError("Konfigurasi autentikasi belum tersedia."); setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); if (!data.session) setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);
  useEffect(() => { if (session) void load(); }, [session, load]);

  async function openPreview(item: Content) {
    setPreviewId(item.id); setError("");
    try {
      const payload = await request(`/v1/content/${encodeURIComponent(item.id)}/preview`) as { media?: { preview_url?: string; signed_url?: string; id?: string }[] };
      const urls = (payload.media ?? []).map(media => media.preview_url ?? media.signed_url).filter((url): url is string => Boolean(url));
      if (!urls.length) throw new Error("Konten belum memiliki media preview yang tersedia.");
      setPreviewUrls(current => ({ ...current, [item.id]: urls[0] }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Preview tidak dapat dibuka."); }
    finally { setPreviewId(""); }
  }

  const filtered = items.filter(item => (filter === "all" || item.content_type === filter) && ["video", "audio"].includes(item.content_type));
  if (!session && !loading) return <main className="mx-auto w-full max-w-5xl px-4 py-12"><section className="rounded-3xl border border-slate-200 bg-white p-8"><Film className="text-blue-700" size={28}/><h1 className="mt-4 text-2xl font-bold text-slate-950">Allpha AI Cinema</h1><p className="mt-2 text-slate-600">Masuk untuk membuka pustaka konten video dan audio milik Anda.</p><Link href="/" className="mt-5 inline-flex rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white">Masuk ke Allpha</Link></section></main>;

  return <main className="mx-auto w-full max-w-5xl px-4 pb-28 pt-5 sm:px-6 sm:pt-8">
    <nav aria-label="Fitur Allpha" className="mb-4 flex flex-wrap gap-2">{[{href:"/cinema",label:"AI Cinema"},{href:"/live",label:"Live Stage"},{href:"/marketplace",label:"Marketplace"}].map(item=><Link key={item.href} href={item.href} aria-current={typeof window!=="undefined" && window.location.pathname===item.href ? "page" : undefined} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-blue-300 hover:text-blue-700">{item.label}</Link>)}</nav>
    <section className="relative overflow-hidden rounded-[28px] bg-slate-950 px-5 py-7 text-white sm:px-8 sm:py-10">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(37,99,235,.32),transparent_55%)]" aria-hidden="true"/>
      <div className="relative flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[0.24em] text-blue-300">ALLPHA ORIGINALS · CREATOR STUDIO</p><h1 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">AI Cinema</h1><p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">Pustaka konten video dan audio Anda, dengan status konten dan media yang dibaca dari API Allpha.</p></div>
        <Link href="/create" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white hover:bg-blue-500"><Plus size={17}/> Buat konten <ArrowUpRight size={15}/></Link>
      </div>
    </section>
    <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><h2 className="text-lg font-bold text-slate-950">Pustaka saya</h2><p className="mt-1 text-sm text-slate-500">Hanya item milik akun yang sedang masuk; bukan katalog film contoh.</p></div>
      <div className="flex gap-2" role="group" aria-label="Filter tipe media">
        {([{id:"all",label:"Semua"},{id:"video",label:"Video"},{id:"audio",label:"Audio"}] as const).map(tab=><button key={tab.id} onClick={()=>setFilter(tab.id)} aria-pressed={filter===tab.id} className={`rounded-full border px-4 py-2 text-xs font-semibold ${filter===tab.id?"border-blue-700 bg-blue-700 text-white":"border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}>{tab.label}</button>)}
      </div>
    </div>
    {error && <div role="alert" className="mt-4 flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><span>{error}</span><button onClick={()=>void load()} className="inline-flex shrink-0 items-center gap-1 font-semibold underline"><RefreshCw size={14}/> Coba lagi</button></div>}
    {loading && <div className="mt-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600"><LoaderCircle className="animate-spin" size={18}/> Memuat pustaka konten…</div>}
    {!loading && !error && filtered.length===0 && <section className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center"><Film className="mx-auto text-slate-400" size={30}/><h3 className="mt-3 font-bold text-slate-900">Belum ada konten {filter==="all"?"video atau audio":filter}</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">Konten yang Anda buat melalui alur Create akan muncul di sini jika tipenya video atau audio. Generator film AI dan job rendering khusus belum tersedia sebagai kontrak backend.</p><Link href="/create" className="mt-5 inline-flex items-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white"><Plus size={16}/> Buka Create</Link></section>}
    <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {filtered.map(item=><article key={item.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="relative grid aspect-video place-items-center bg-slate-950 text-blue-200">{item.content_type==="video"?<Video size={34}/>:<AudioLines size={34}/>}<span className="absolute left-3 top-3 rounded-full border border-white/15 bg-black/50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white">{item.content_type}</span><span className="absolute bottom-3 right-3 rounded-full bg-black/50 px-2 py-1 text-[10px] text-white">{item.status}</span></div>
        <div className="p-4"><h3 className="line-clamp-2 font-bold text-slate-950">{item.body.trim() || item.media?.[0]?.filename || "Konten tanpa judul"}</h3><p className="mt-2 text-xs text-slate-500">Diperbarui {new Date(item.updated_at).toLocaleDateString("id-ID")} · Moderasi: {item.moderation_status ?? "belum dikirim"}</p>
          {previewUrls[item.id] && <div className="mt-3">{item.content_type==="video"?<video controls playsInline src={previewUrls[item.id]} className="w-full rounded-xl bg-black"/>:<audio controls src={previewUrls[item.id]} className="w-full"/>}</div>}
          <button disabled={previewId===item.id} onClick={()=>void openPreview(item)} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">{previewId===item.id?<LoaderCircle className="animate-spin" size={15}/>:<Play size={15}/>} Buka preview</button>
          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-slate-500"><ShieldCheck size={13}/> Media privat menggunakan URL preview berumur pendek.</p>
        </div>
      </article>)}
    </div>
  </main>;
}
