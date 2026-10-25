"use client";

import { useState } from "react";
import {
  Bookmark,
  Check,
  ChevronDown,
  Heart,
  MessageCircle,
  MoreHorizontal,
  Repeat2,
  Send,
  Share2,
  ShieldAlert,
} from "lucide-react";

type FeedMedia = { id: string; filename: string; media_type: string; preview_url?: string | null };
type FeedItem = {
  id: string; owner_id: string; body: string; content_type: string; visibility: string;
  published_at?: string | null; created_at: string; media?: FeedMedia[];
  engagement?: { likes: number; comments: number; saves: number; shares?: number };
  viewer_reaction?: string | null; saved?: boolean; ranking_signals?: string[];
};
type FeedComment = { id: string; actor_user_id: string; body: string; created_at: string };
type ReportReason = "spam" | "harassment" | "privacy" | "misinformation" | "other";

type Props = {
  item: FeedItem;
  comments: FeedComment[];
  commentsOpen: boolean;
  commentDraft: string;
  reportReason: ReportReason;
  busy: boolean;
  onToggleReaction: (item: FeedItem) => void;
  onToggleSave: (item: FeedItem) => void;
  onOpenComments: (item: FeedItem) => void;
  onShare: (item: FeedItem) => void;
  onReport: (item: FeedItem) => void;
  onReportReasonChange: (reason: ReportReason) => void;
  onCommentDraftChange: (value: string) => void;
  onSubmitComment: (item: FeedItem) => void;
};

const reportReasons: { value: ReportReason; label: string }[] = [
  { value: "spam", label: "Spam" },
  { value: "harassment", label: "Pelecehan" },
  { value: "privacy", label: "Privasi" },
  { value: "misinformation", label: "Misinformasi" },
  { value: "other", label: "Lainnya" },
];

export default function FeedPostCard({
  item, comments, commentsOpen, commentDraft, reportReason, busy,
  onToggleReaction, onToggleSave, onOpenComments, onShare, onReport,
  onReportReasonChange, onCommentDraftChange, onSubmitComment,
}: Props) {
  const [reportMenuOpen, setReportMenuOpen] = useState(false);
  const timestamp = new Date(item.published_at ?? item.created_at);
  const ownerInitial = item.owner_id.trim().slice(0, 1).toUpperCase() || "A";
  const ownerHandle = item.owner_id.length > 12 ? item.owner_id.slice(0, 8) + "…" : item.owner_id;

  return (
    <article className="allpha-feed-card w-full min-w-0 space-y-3.5 rounded-[28px] border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a] sm:p-5">
      <header className="flex min-w-0 items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 border-slate-900 bg-sky-100 text-sm font-black text-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]" aria-hidden="true">
            {ownerInitial}
          </span>
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5">
              <strong className="max-w-full break-all text-sm font-extrabold text-slate-900">Creator</strong>
              <span className="break-all text-xs font-semibold text-slate-500">@{ownerHandle}</span>
            </div>
            <time className="block pt-0.5 text-[11px] font-medium text-slate-500" dateTime={timestamp.toISOString()}>
              {Number.isNaN(timestamp.getTime()) ? "Waktu tidak tersedia" : timestamp.toLocaleString("id-ID")}
            </time>
          </div>
        </div>

        <div className="relative shrink-0">
          <button
            type="button"
            aria-label="Opsi laporan konten"
            aria-expanded={reportMenuOpen}
            onClick={() => setReportMenuOpen(open => !open)}
            className="grid h-9 w-9 place-items-center rounded-full border-2 border-slate-900 bg-white text-slate-800 transition hover:bg-slate-100 active:translate-x-0.5 active:translate-y-0.5"
          >
            <MoreHorizontal className="h-5 w-5" />
          </button>
          {reportMenuOpen && (
            <div className="absolute right-0 top-11 z-20 w-56 rounded-2xl border-2 border-slate-900 bg-white p-3 shadow-[3px_3px_0px_#0f172a]">
              <label className="mb-1.5 block text-[11px] font-extrabold text-slate-700" htmlFor={`report-${item.id}`}>Alasan laporan</label>
              <div className="relative">
                <select
                  id={`report-${item.id}`}
                  value={reportReason}
                  onChange={event => onReportReasonChange(event.target.value as ReportReason)}
                  className="w-full appearance-none rounded-xl border-2 border-slate-900 bg-white px-3 py-2 pr-8 text-xs font-semibold text-slate-800 outline-none focus:ring-2 focus:ring-sky-300"
                >
                  {reportReasons.map(reason => <option key={reason.value} value={reason.value}>{reason.label}</option>)}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-slate-600" />
              </div>
              <button
                type="button"
                onClick={() => { onReport(item); setReportMenuOpen(false); }}
                disabled={busy}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-full border-2 border-slate-900 bg-rose-50 px-3 py-2 text-xs font-extrabold text-rose-700 transition hover:bg-rose-100 disabled:opacity-50"
              >
                <ShieldAlert className="h-3.5 w-3.5" /> Laporkan konten
              </button>
            </div>
          )}
        </div>
      </header>

      {item.body && (
        <p className="cursor-text whitespace-pre-line break-words text-sm font-medium leading-relaxed text-slate-900">
          {item.body}
        </p>
      )}

      {item.media?.map(media => media.preview_url && (
        <div className="group relative min-w-0 overflow-hidden rounded-2xl border-2 border-slate-900 bg-slate-950 shadow-[2px_2px_0px_#0f172a]" key={media.id}>
          {media.media_type.startsWith("video/")
            ? <video className="max-h-[560px] w-full object-contain" src={media.preview_url} controls playsInline preload="metadata" aria-label={media.filename} />
            : media.media_type.startsWith("audio/")
              ? <div className="bg-slate-50 p-4"><audio className="w-full" src={media.preview_url} controls preload="metadata" aria-label={media.filename} /></div>
              : <img className="max-h-[560px] w-full object-contain" src={media.preview_url} alt={media.filename} loading="lazy" />}
          <span className="absolute bottom-2 left-2 max-w-[80%] truncate rounded-full border border-white/70 bg-white/95 px-2.5 py-1 text-[10px] font-bold text-slate-800 backdrop-blur">{media.filename}</span>
        </div>
      ))}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t-2 border-slate-100 pt-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs font-bold text-slate-700">
          <button type="button" className={`inline-flex items-center gap-1.5 transition hover:text-rose-600 ${item.viewer_reaction ? "text-rose-600" : ""}`} onClick={() => onToggleReaction(item)} disabled={busy} aria-pressed={Boolean(item.viewer_reaction)}>
            <Heart className={`h-[18px] w-[18px] ${item.viewer_reaction ? "fill-rose-500 text-rose-500" : ""}`} />
            <span>{item.engagement?.likes ?? 0}</span>
          </button>
          <button type="button" className="inline-flex items-center gap-1.5 transition hover:text-blue-600" onClick={() => onOpenComments(item)} aria-expanded={commentsOpen}>
            <MessageCircle className="h-[18px] w-[18px]" />
            <span>{item.engagement?.comments ?? 0}</span>
          </button>
          <button type="button" className={`inline-flex items-center gap-1.5 transition hover:text-emerald-700 ${item.saved ? "text-emerald-700" : ""}`} onClick={() => onToggleSave(item)} disabled={busy} aria-pressed={Boolean(item.saved)}>
            {item.saved ? <Check className="h-[18px] w-[18px]" /> : <Bookmark className="h-[18px] w-[18px]" />}
            <span>{item.engagement?.saves ?? 0}</span>
          </button>
          <button type="button" className="inline-flex items-center gap-1.5 transition hover:text-slate-950" onClick={() => onShare(item)} disabled={busy}>
            <Share2 className="h-[18px] w-[18px]" />
            <span>{item.engagement?.shares ?? 0}</span>
          </button>
        </div>
        <button type="button" onClick={() => onShare(item)} disabled={busy} className="inline-flex items-center gap-1.5 rounded-full border-2 border-slate-900 bg-sky-50 px-3 py-1.5 text-xs font-extrabold text-sky-800 shadow-[1.5px_1.5px_0px_#0f172a] transition hover:bg-sky-100 active:translate-x-0.5 active:translate-y-0.5 disabled:opacity-50">
          <Send className="h-3.5 w-3.5" /> Bagikan
        </button>
      </div>

      {commentsOpen && (
        <section className="space-y-3 border-t-2 border-slate-100 pt-3" aria-label="Komentar konten">
          <div className="space-y-2">
            {comments.map(comment => (
              <div className="flex min-w-0 items-start gap-2.5 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs" key={comment.id}>
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-slate-900 bg-white text-[10px] font-black text-slate-800" aria-hidden="true">{comment.actor_user_id.slice(0, 1).toUpperCase() || "A"}</span>
                <div className="min-w-0 flex-1">
                  <p className="break-all font-extrabold text-slate-900">{comment.actor_user_id.slice(0, 8)} <span className="font-medium text-slate-500">· {new Date(comment.created_at).toLocaleString("id-ID")}</span></p>
                  <p className="mt-1 whitespace-pre-line break-words text-slate-700">{comment.body}</p>
                </div>
              </div>
            ))}
            {!comments.length && <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500">Belum ada komentar pada konten ini.</p>}
          </div>
          <form className="flex min-w-0 items-center gap-2" onSubmit={event => { event.preventDefault(); onSubmitComment(item); }}>
            <label className="sr-only" htmlFor={`comment-${item.id}`}>Tulis komentar</label>
            <input id={`comment-${item.id}`} className="min-w-0 flex-1 rounded-full border-2 border-slate-900 bg-slate-50 px-3.5 py-2.5 text-xs font-medium outline-none transition focus:bg-white focus:ring-2 focus:ring-sky-200" value={commentDraft} onChange={event => onCommentDraftChange(event.target.value)} maxLength={2000} placeholder="Tulis komentar publik…" />
            <button type="submit" disabled={busy || !commentDraft.trim()} className="rounded-full border-2 border-slate-900 bg-slate-900 px-4 py-2.5 text-xs font-extrabold text-white shadow-[1.5px_1.5px_0px_#0f172a] transition hover:bg-slate-800 active:translate-x-0.5 active:translate-y-0.5 disabled:opacity-50">Kirim</button>
          </form>
        </section>
      )}
    </article>
  );
}
