"use client";

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

export default function FeedPostCard({
  item, comments, commentsOpen, commentDraft, reportReason, busy,
  onToggleReaction, onToggleSave, onOpenComments, onShare, onReport,
  onReportReasonChange, onCommentDraftChange, onSubmitComment,
}: Props) {
  const timestamp = new Date(item.published_at ?? item.created_at);
  return (
    <article className="allpha-feed-card">
      <div className="allpha-feed-card-meta">
        <div className="allpha-feed-owner">
          <span className="allpha-feed-owner-mark" aria-hidden="true">A</span>
          <div>
            <strong>Creator · {item.owner_id.slice(0, 8)}</strong>
            <time dateTime={timestamp.toISOString()}>{timestamp.toLocaleString("id-ID")}</time>
          </div>
        </div>
        <div className="allpha-feed-report">
          <label className="sr-only" htmlFor={`report-${item.id}`}>Alasan laporan konten</label>
          <select id={`report-${item.id}`} value={reportReason} onChange={event => onReportReasonChange(event.target.value as ReportReason)} aria-label="Alasan laporan konten">
            <option value="spam">Spam</option><option value="harassment">Pelecehan</option><option value="privacy">Privasi</option><option value="misinformation">Misinformasi</option><option value="other">Lainnya</option>
          </select>
          <button type="button" onClick={() => onReport(item)} disabled={busy}>Laporkan</button>
        </div>
      </div>
      {item.body && <p className="allpha-feed-card-body">{item.body}</p>}
      {item.media?.map(media => media.preview_url && (
        <div className="allpha-feed-media" key={media.id}>
          {media.media_type.startsWith("video/")
            ? <video src={media.preview_url} controls playsInline preload="metadata" aria-label={media.filename} />
            : media.media_type.startsWith("audio/")
              ? <audio src={media.preview_url} controls preload="metadata" aria-label={media.filename} />
              : <img src={media.preview_url} alt={media.filename} loading="lazy" />}
        </div>
      ))}
      <div className="allpha-feed-actions" aria-label="Aksi konten">
        <button type="button" className={item.viewer_reaction ? "is-selected" : ""} onClick={() => onToggleReaction(item)} disabled={busy} aria-pressed={Boolean(item.viewer_reaction)}><span aria-hidden="true">♡</span> {item.engagement?.likes ?? 0}</button>
        <button type="button" className={item.saved ? "is-selected" : ""} onClick={() => onToggleSave(item)} disabled={busy} aria-pressed={Boolean(item.saved)}><span aria-hidden="true">▣</span> {item.saved ? "Tersimpan" : "Simpan"} · {item.engagement?.saves ?? 0}</button>
        <button type="button" onClick={() => onOpenComments(item)} aria-expanded={commentsOpen}><span aria-hidden="true">◯</span> {commentsOpen ? "Tutup komentar" : "Komentar"} · {item.engagement?.comments ?? 0}</button>
        <button type="button" onClick={() => onShare(item)} disabled={busy}><span aria-hidden="true">↗</span> Bagikan · {item.engagement?.shares ?? 0}</button>
      </div>
      {commentsOpen && <div className="allpha-feed-comments">
        {comments.map(comment => <div className="allpha-feed-comment" key={comment.id}><p className="allpha-feed-comment-meta">{comment.actor_user_id.slice(0, 8)} · {new Date(comment.created_at).toLocaleString("id-ID")}</p><p>{comment.body}</p></div>)}
        {!comments.length && <p className="allpha-feed-empty-comments">Belum ada komentar pada konten ini.</p>}
        <form className="allpha-feed-comment-form" onSubmit={event => { event.preventDefault(); onSubmitComment(item); }}>
          <label className="sr-only" htmlFor={`comment-${item.id}`}>Tulis komentar</label>
          <input id={`comment-${item.id}`} value={commentDraft} onChange={event => onCommentDraftChange(event.target.value)} maxLength={2000} placeholder="Tulis komentar…" />
          <button type="submit" disabled={busy || !commentDraft.trim()}>Kirim</button>
        </form>
      </div>}
    </article>
  );
}
