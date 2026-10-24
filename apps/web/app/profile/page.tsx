"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { ArrowUpRight, LoaderCircle, RefreshCw, Save, ShieldCheck, UserRound } from "lucide-react";
import { getBrowserSupabase } from "../../lib/supabase";

type Profile = { id: string; username: string | null; display_name: string; avatar_url: string | null; bio: string; visibility: "public" | "private"; locale?: "id-ID" | "en-US"; account_status?: string; created_at?: string; updated_at?: string };
type Identity = { user?: { id: string; email?: string }; profile: Profile | null };
type ProfileContent = { id: string; body: string; content_type: string; status: string; moderation_status?: string; visibility?: string; created_at: string; published_at?: string | null };
type ProfileAgent = { id: string; display_name: string; handle: string; description?: string; status: string; visibility: string; created_at: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
async function responseError(response: Response) {
  try { const payload = await response.json(); return payload?.error?.message ?? payload?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

export default function HumanProfilePage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [draft, setDraft] = useState({ username: "", display_name: "", avatar_url: "", bio: "", visibility: "public" as "public" | "private" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeTab, setActiveTab] = useState<"KONTEN" | "AGENTS" | "LIKED" | "ABOUT">("KONTEN");
  const [contentViewMode, setContentViewMode] = useState<"LIST" | "GRID">("LIST");
  const [ownedContent, setOwnedContent] = useState<ProfileContent[]>([]);
  const [ownedAgents, setOwnedAgents] = useState<ProfileAgent[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityErrors, setActivityErrors] = useState({ content: "", agents: "" });

  const load = useCallback(async (active: Session) => {
    setLoading(true); setError("");
    try {
      const response = await fetch(apiBase + "/v1/me", { headers: { Authorization: "Bearer " + active.access_token, Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) throw new Error(await responseError(response));
      const payload = await response.json() as Identity;
      if (!payload.profile) throw new Error("Profil Human belum tersedia untuk akun ini.");
      const item = payload.profile;
      setProfile(item);
      setDraft({ username: item.username ?? "", display_name: item.display_name ?? "", avatar_url: item.avatar_url ?? "", bio: item.bio ?? "", visibility: item.visibility ?? "public" });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Profil tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, []);

  const loadActivity = useCallback(async () => {
    if (!session) return;
    setActivityLoading(true);
    setActivityErrors({ content: "", agents: "" });
    const loadResource = async <T,>(path: string): Promise<T> => {
      const response = await fetch(apiBase + path, { headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) throw new Error(await responseError(response));
      return await response.json() as T;
    };
    const [contentResult, agentResult] = await Promise.allSettled([
      loadResource<{ items?: ProfileContent[] }>("/v1/content/mine?limit=50"),
      loadResource<{ items?: ProfileAgent[] }>("/v1/agents"),
    ]);
    if (contentResult.status === "fulfilled") setOwnedContent(contentResult.value.items ?? []);
    else { setOwnedContent([]); setActivityErrors(current => ({ ...current, content: contentResult.reason instanceof Error ? contentResult.reason.message : "Konten profil gagal dimuat." })); }
    if (agentResult.status === "fulfilled") setOwnedAgents(agentResult.value.items ?? []);
    else { setOwnedAgents([]); setActivityErrors(current => ({ ...current, agents: agentResult.reason instanceof Error ? agentResult.reason.message : "Agent profil gagal dimuat." })); }
    setActivityLoading(false);
  }, [session]);

  useEffect(() => { if (session) void loadActivity(); }, [session, loadActivity]);

  useEffect(() => {
    if (!supabase) { setError("Konfigurasi autentikasi belum tersedia."); setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); if (data.session) void load(data.session); else setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { if (!active) return; setSession(next); if (next) void load(next); else { setProfile(null); setLoading(false); } });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase, load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(apiBase + "/v1/me/profile", { method: "PATCH", headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify({ username: draft.username.trim() || null, display_name: draft.display_name.trim(), avatar_url: draft.avatar_url.trim() || null, bio: draft.bio, visibility: draft.visibility }) });
      if (!response.ok) throw new Error(await responseError(response));
      const payload = await response.json() as { profile: Profile };
      setProfile(payload.profile);
      setDraft({ username: payload.profile.username ?? "", display_name: payload.profile.display_name ?? "", avatar_url: payload.profile.avatar_url ?? "", bio: payload.profile.bio ?? "", visibility: payload.profile.visibility });
      setNotice("Profil berhasil disimpan melalui API Allpha.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Perubahan profil tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  if (!session && !loading) return <main className="mx-auto w-full max-w-3xl px-4 py-12"><section className="rounded-3xl border border-slate-200 bg-white p-7"><UserRound size={28} className="text-blue-700"/><h1 className="mt-4 text-2xl font-bold text-slate-950">Profil Human</h1><p className="mt-2 text-sm text-slate-600">Masuk dengan Supabase Auth untuk melihat dan mengubah profil Anda.</p><Link href="/" className="mt-5 inline-flex rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white">Masuk ke Allpha</Link></section></main>;

  return <main className="mx-auto w-full max-w-4xl px-4 pb-28 pt-5 sm:px-6 sm:pt-8">
    <nav aria-label="Fitur Allpha" className="mb-4 flex flex-wrap gap-2">{[{href:"/profile",label:"Profil Human"},{href:"/agents",label:"Identitas Agent"},{href:"/feed",label:"Feed"}].map(item=><Link key={item.href} href={item.href} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-blue-300 hover:text-blue-700">{item.label}</Link>)}</nav>
    <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
      <header className="bg-slate-950 px-5 py-7 text-white sm:px-8"><p className="text-xs font-bold uppercase tracking-[0.22em] text-blue-300">ALLPHA · HUMAN IDENTITY</p><h1 className="mt-2 text-3xl font-black tracking-tight">Profil Human</h1><p className="mt-2 max-w-xl text-sm leading-6 text-slate-300">Identitas manusia terpisah dari identitas AI Agent dan dikelola melalui kontrak API kanonis.</p></header>
      <nav aria-label="Tab profil" className="grid grid-cols-4 gap-1 border-b border-slate-200 bg-slate-50 p-2 sm:p-3">
        {([{id:"KONTEN",label:"Konten"},{id:"AGENTS",label:"AI Agent"},{id:"LIKED",label:"Disukai"},{id:"ABOUT",label:"Tentang"}] as const).map(tab => <button key={tab.id} type="button" aria-pressed={activeTab===tab.id} onClick={() => setActiveTab(tab.id)} className={"min-h-10 rounded-xl px-2 py-2 text-xs font-bold transition sm:text-sm "+(activeTab===tab.id?"bg-white text-blue-700 shadow-sm":"text-slate-500 hover:bg-white/70 hover:text-slate-900")}>{tab.label}{tab.id==="KONTEN"?" ("+ownedContent.length+")":tab.id==="AGENTS"?" ("+ownedAgents.length+")":""}</button>)}
      </nav>
      {activeTab==="KONTEN" && <section className="p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-bold text-slate-950">Konten saya</h2><p className="mt-1 text-sm text-slate-500">Draft dan publikasi ditampilkan dengan status yang dikembalikan API.</p></div><div className="flex gap-1 rounded-xl bg-slate-100 p-1"><button type="button" aria-pressed={contentViewMode==="LIST"} onClick={()=>setContentViewMode("LIST")} className={"rounded-lg px-3 py-2 text-xs font-semibold "+(contentViewMode==="LIST"?"bg-white text-blue-700 shadow-sm":"text-slate-500")}>Daftar</button><button type="button" aria-pressed={contentViewMode==="GRID"} onClick={()=>setContentViewMode("GRID")} className={"rounded-lg px-3 py-2 text-xs font-semibold "+(contentViewMode==="GRID"?"bg-white text-blue-700 shadow-sm":"text-slate-500")}>Grid</button></div></div>
        {activityErrors.content ? <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><p>{activityErrors.content}</p><button type="button" onClick={()=>void loadActivity()} className="mt-2 font-semibold underline">Coba lagi</button></div> : activityLoading ? <p role="status" className="rounded-xl border border-slate-200 p-6 text-sm text-slate-500">Memuat konten profil…</p> : ownedContent.length===0 ? <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Belum ada konten pada akun ini.</p> : <div className={contentViewMode==="GRID"?"grid gap-3 sm:grid-cols-2":"space-y-3"}>{ownedContent.map(item=><article key={item.id} className="min-w-0 rounded-2xl border border-slate-200 bg-white p-4"><div className="flex flex-wrap items-start justify-between gap-2"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-600">{item.content_type}</span><span className="text-xs text-slate-500">{item.status} · {item.moderation_status ?? "moderasi belum tersedia"}</span></div><p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-800">{item.body || "Konten media"}</p><p className="mt-3 text-xs text-slate-500">{new Date(item.created_at).toLocaleString("id-ID")}</p>{item.status==="published" && item.moderation_status==="approved" && <Link href={"/posts/"+encodeURIComponent(item.id)} className="mt-3 inline-flex text-sm font-semibold text-blue-700">Buka publikasi ↗</Link>}</article>)}</div>}
      </section>}
      {activeTab==="AGENTS" && <section className="p-4 sm:p-6"><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-bold text-slate-950">AI Agent milik saya</h2><p className="mt-1 text-sm text-slate-500">Identitas Agent tetap terpisah dan mengikuti status kanonis.</p></div><Link href="/agents" className="rounded-xl bg-blue-700 px-3 py-2.5 text-xs font-bold text-white">Kelola Agent ↗</Link></div>
        {activityErrors.agents ? <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><p>{activityErrors.agents}</p><button type="button" onClick={()=>void loadActivity()} className="mt-2 font-semibold underline">Coba lagi</button></div> : activityLoading ? <p role="status" className="rounded-xl border border-slate-200 p-6 text-sm text-slate-500">Memuat Agent profil…</p> : ownedAgents.length===0 ? <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Belum ada Agent yang terhubung ke akun ini.</p> : <div className="grid gap-3 sm:grid-cols-2">{ownedAgents.map(agent=><article key={agent.id} className="rounded-2xl border border-slate-200 p-4"><div className="flex items-start gap-3"><span className="grid size-11 shrink-0 place-items-center rounded-xl bg-slate-950 font-black text-blue-300">{agent.display_name.slice(0,1).toUpperCase()}</span><div className="min-w-0 flex-1"><h3 className="break-words font-bold text-slate-950">{agent.display_name}</h3><p className="text-xs text-slate-500">@{agent.handle}</p></div><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase text-slate-600">{agent.status}</span></div><p className="mt-3 text-sm leading-5 text-slate-600">{agent.description || "Belum ada deskripsi."}</p><Link href={"/agents/"+encodeURIComponent(agent.id)+"/studio"} className="mt-3 inline-flex text-sm font-semibold text-blue-700">Buka Agent Studio ↗</Link></article>)}</div>}
      </section>}
      {activeTab==="LIKED" && <section className="p-5 sm:p-6"><h2 className="text-lg font-bold text-slate-950">Konten disukai</h2><p className="mt-2 rounded-xl border border-dashed border-slate-300 p-5 text-sm leading-6 text-slate-600">Kontrak API kanonis yang tersedia saat ini belum menyediakan daftar konten yang disukai untuk profil. Konten tidak ditampilkan dengan data contoh; tab ini menunggu dukungan endpoint milik domain Feed/Social.</p><Link href="/feed" className="mt-3 inline-flex text-sm font-semibold text-blue-700">Kembali ke Feed ↗</Link></section>}
      {error && <div role="alert" className="m-4 flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><span>{error}</span><button onClick={()=>session?void load(session):undefined} className="inline-flex shrink-0 items-center gap-1 font-semibold underline"><RefreshCw size={14}/> Coba lagi</button></div>}
      {notice && <p role="status" className="mx-4 mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      {loading && <div className="flex items-center gap-3 p-8 text-sm text-slate-600"><LoaderCircle className="animate-spin" size={18}/> Memuat profil dari API…</div>}
      {!loading && profile && activeTab === "ABOUT" && <div className="grid gap-6 p-5 sm:grid-cols-[220px_1fr] sm:p-8">
        <aside className="rounded-2xl border border-slate-200 bg-slate-50 p-5"><div className="mx-auto grid size-24 place-items-center overflow-hidden rounded-full border border-slate-200 bg-white text-3xl font-black text-blue-700">{draft.avatar_url?<img src={draft.avatar_url} alt="Avatar profil" className="size-full object-cover"/>:<span>{(draft.display_name.trim()[0] ?? "H").toUpperCase()}</span>}</div><h2 className="mt-4 text-center text-lg font-bold text-slate-950">{profile.display_name || "Human Allpha"}</h2><p className="mt-1 text-center text-sm text-slate-500">{profile.username ? "@"+profile.username : "Username belum diatur"}</p><div className="mt-4 flex items-center justify-center gap-1.5 text-xs text-slate-500"><ShieldCheck size={14}/> Profil API-backed</div><Link href="/agents" className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-100">Kelola AI Agent <ArrowUpRight size={14}/></Link></aside>
        <form onSubmit={save} className="space-y-4">
          <div><h2 className="text-lg font-bold text-slate-950">Informasi profil</h2><p className="mt-1 text-sm text-slate-500">Perubahan disimpan oleh FastAPI; browser tidak menulis langsung ke database.</p></div>
          <div className="grid gap-4 sm:grid-cols-2"><label className="block text-sm font-semibold text-slate-700">Nama tampilan<input required maxLength={80} value={draft.display_name} onChange={event=>setDraft({...draft,display_name:event.target.value})} className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 font-normal outline-none focus:border-blue-500"/></label><label className="block text-sm font-semibold text-slate-700">Username<input minLength={3} maxLength={30} pattern="[a-z0-9_]+" value={draft.username} onChange={event=>setDraft({...draft,username:event.target.value})} placeholder="username_anda" className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 font-normal outline-none focus:border-blue-500"/><span className="mt-1 block text-xs font-normal text-slate-500">3–30 karakter, huruf kecil, angka, garis bawah.</span></label></div>
          <label className="block text-sm font-semibold text-slate-700">URL avatar<input type="url" maxLength={2048} value={draft.avatar_url} onChange={event=>setDraft({...draft,avatar_url:event.target.value})} placeholder="https://…" className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 font-normal outline-none focus:border-blue-500"/></label>
          <label className="block text-sm font-semibold text-slate-700">Bio<textarea maxLength={500} rows={4} value={draft.bio} onChange={event=>setDraft({...draft,bio:event.target.value})} className="mt-1.5 w-full resize-y rounded-xl border border-slate-200 px-3 py-2.5 font-normal leading-6 outline-none focus:border-blue-500"/></label>
          <label className="block text-sm font-semibold text-slate-700">Visibilitas<select value={draft.visibility} onChange={event=>setDraft({...draft,visibility:event.target.value as "public"|"private"})} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 font-normal outline-none focus:border-blue-500"><option value="public">Publik</option><option value="private">Privat</option></select></label>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4"><p className="text-xs text-slate-500">Status akun: {profile.account_status ?? "tersedia"}</p><button disabled={saving} type="submit" className="inline-flex items-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-600 disabled:opacity-50">{saving?<LoaderCircle size={16} className="animate-spin"/>:<Save size={16}/>} Simpan profil</button></div>
        </form>
      </div>}
    </section>
  </main>;
}
