"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../lib/supabase";

type Profile = {
  id: string;
  username: string;
  display_name: string;
  avatar_url?: string | null;
  bio?: string;
  visibility: "public" | "private";
  created_at?: string;
};
type Media = { id: string; media_type?: string; filename?: string; preview_url?: string | null };
type ProfilePost = {
  id: string;
  body: string;
  created_at: string;
  published_at?: string | null;
  media?: Media[];
  engagement?: { likes: number; comments: number; shares: number };
};
type ProfilePayload = {
  profile: Profile;
  items: ProfilePost[];
  count: number;
  can_view_content: boolean;
  follow_status: "active" | "requested" | null;
  is_self: boolean;
  detail?: { code?: string; message?: string };
  error?: { message?: string };
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

export default function PublicProfilePage() {
  const params = useParams<{ username: string }>();
  const router = useRouter();
  const username = typeof params?.username === "string" ? decodeURIComponent(params.username) : "";
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [data, setData] = useState<ProfilePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const requestSequence = useRef(0);

  useEffect(() => {
    if (!supabase) { setSessionReady(true); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data: result }) => {
      if (active) { setSession(result.session); setSessionReady(true); }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      requestSequence.current += 1;
      setData(null);
      setSession(next);
      setSessionReady(true);
    });
    return () => {
      active = false;
      requestSequence.current += 1;
      listener.subscription.unsubscribe();
    };
  }, [supabase]);

  const loadProfile = useCallback(async () => {
    if (!sessionReady || !username) return;
    const sequence = ++requestSequence.current;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiBase + "/v1/social/profiles/" + encodeURIComponent(username), {
        headers: session ? { Authorization: "Bearer " + session.access_token, Accept: "application/json" } : { Accept: "application/json" },
        cache: "no-store",
      });
      const payload = await response.json().catch(() => ({})) as ProfilePayload;
      if (!response.ok) throw new Error(payload.detail?.message || payload.error?.message || "Profil tidak tersedia atau tidak dapat diakses.");
      if (sequence !== requestSequence.current) return;
      setData(payload);
    } catch (cause) {
      if (sequence === requestSequence.current) {
        setData(null);
        setError(cause instanceof Error ? cause.message : "Profil tidak dapat dimuat.");
      }
    } finally {
      if (sequence === requestSequence.current) setLoading(false);
    }
  }, [session, sessionReady, username]);

  useEffect(() => { void loadProfile(); }, [loadProfile]);

  async function toggleFollow() {
    if (!data || data.is_self || !session) {
      if (!session) router.push("/login?next=" + encodeURIComponent("/profile/" + username));
      return;
    }
    const targetId = data.profile.id;
    const cancel = data.follow_status === "active" || data.follow_status === "requested";
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch(cancel
        ? apiBase + "/v1/me/social-edges/" + encodeURIComponent(targetId) + "/follow"
        : apiBase + "/v1/me/social-edges", {
        method: cancel ? "DELETE" : "POST",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json", Accept: "application/json" },
        body: cancel ? undefined : JSON.stringify({ target_user_id: targetId, edge_type: "follow" }),
        cache: "no-store",
      });
      const result = await response.json().catch(() => ({})) as { outcome?: string; detail?: { message?: string }; error?: { message?: string } };
      if (!response.ok) throw new Error(result.detail?.message || result.error?.message || "Status mengikuti akun tidak dapat diubah.");
      if (cancel) {
        setData(current => current ? { ...current, follow_status: null, can_view_content: current.profile.visibility === "public" || current.is_self } : current);
        setNotice("Status mengikuti dibatalkan.");
      } else if (result.outcome === "follow_request_created") {
        setData(current => current ? { ...current, follow_status: "requested" } : current);
        setNotice("Permintaan mengikuti profil privat telah dikirim.");
      } else {
        setData(current => current ? { ...current, follow_status: "active" } : current);
        setNotice("Anda sekarang mengikuti profil ini.");
        await loadProfile();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Status mengikuti akun tidak dapat diubah.");
    } finally { setBusy(false); }
  }

  return (
    <main className="min-h-[80dvh] bg-[#F4F7FB] px-3 py-5 text-slate-900 sm:px-5">
      <div className="mx-auto max-w-2xl space-y-4">
        <div className="flex items-center justify-between">
          <a href="/search" className="rounded-xl border-2 border-slate-900 bg-white px-3 py-2 text-sm font-bold shadow-[2px_2px_0px_#0f172a]">← Kembali ke pencarian</a>
          <span className="text-xs font-black tracking-wide text-slate-500">ALLPHA UNIVERSE</span>
        </div>

        {loading && <section className="rounded-2xl border-2 border-slate-900 bg-white p-6 shadow-[3px_3px_0px_#0f172a]" role="status">Memuat profil…</section>}
        {!loading && error && <section className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-6 shadow-[3px_3px_0px_#0f172a]"><h1 className="text-lg font-black">Profil tidak tersedia</h1><p className="text-sm text-slate-600">{error}</p><button onClick={() => void loadProfile()} className="rounded-xl border-2 border-slate-900 bg-sky-200 px-4 py-2 text-sm font-black">Coba lagi</button></section>}

        {!loading && !error && data && <>
          <section className="rounded-2xl border-2 border-slate-900 bg-white p-5 shadow-[3px_3px_0px_#0f172a] sm:p-7">
            <div className="flex items-start gap-4">
              {data.profile.avatar_url
                ? <img src={data.profile.avatar_url} alt="" className="h-20 w-20 shrink-0 rounded-2xl border-2 border-slate-900 object-cover" />
                : <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl border-2 border-slate-900 bg-sky-100 text-2xl font-black">{(data.profile.display_name || data.profile.username).slice(0, 1).toUpperCase()}</div>}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="break-words text-2xl font-black">{data.profile.display_name || data.profile.username}</h1>
                  <span className="rounded-lg border border-slate-300 bg-slate-50 px-2 py-1 text-[10px] font-black uppercase tracking-wide">{data.profile.visibility === "private" ? "Profil privat" : "Profil publik"}</span>
                </div>
                <p className="mt-1 text-sm font-semibold text-slate-500">@{data.profile.username.replace(/^@/, "")}</p>
                {data.profile.bio && <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{data.profile.bio}</p>}
                <p className="mt-3 text-xs font-semibold text-slate-500">{data.can_view_content ? data.count + " konten yang dapat dilihat" : "Konten hanya dapat dilihat oleh pengikut yang disetujui."}</p>
              </div>
            </div>
            {!data.is_self && <div className="mt-5 flex flex-wrap items-center gap-3">
              <button disabled={busy} onClick={() => void toggleFollow()} className="rounded-xl border-2 border-slate-900 bg-sky-200 px-4 py-2.5 text-sm font-black shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">
                {busy ? "Memproses…" : data.follow_status === "active" ? "Mengikuti · Batalkan" : data.follow_status === "requested" ? "Permintaan terkirim · Batalkan" : data.profile.visibility === "private" ? "Minta mengikuti" : "Ikuti"}
              </button>
              {notice && <p className="text-sm font-semibold text-emerald-700" role="status">{notice}</p>}
            </div>}
            {error && <p className="mt-3 text-sm font-semibold text-red-700" role="alert">{error}</p>}
          </section>

          {data.can_view_content && <section className="space-y-3">
            <div className="flex items-center justify-between px-1"><h2 className="text-lg font-black">Konten</h2><span className="text-xs font-bold text-slate-500">{data.count} item</span></div>
            {data.items.length === 0 && <div className="rounded-2xl border-2 border-slate-900 bg-white p-5 text-sm text-slate-600">Belum ada konten yang dipublikasikan.</div>}
            {data.items.map(post => <article key={post.id} className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a]">
              <p className="whitespace-pre-wrap break-words text-sm leading-6">{post.body}</p>
              {post.media?.length ? <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">{post.media.map(media => media.preview_url ? <img key={media.id} src={media.preview_url} alt={media.filename || "Media konten"} loading="lazy" className="max-h-80 w-full rounded-xl border border-slate-200 object-contain" /> : null)}</div> : null}
              <div className="flex flex-wrap items-center gap-4 border-t border-slate-100 pt-3 text-xs font-semibold text-slate-500">
                <span>{post.engagement?.likes ?? 0} suka</span><span>{post.engagement?.comments ?? 0} komentar</span><span>{post.engagement?.shares ?? 0} dibagikan</span>
                <time dateTime={post.published_at || post.created_at}>{new Date(post.published_at || post.created_at).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })}</time>
              </div>
            </article>)}
          </section>}
        </>}
      </div>
    </main>
  );
}
