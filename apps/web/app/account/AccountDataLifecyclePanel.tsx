"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type ExportJob = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "expired";
  requested_at: string;
  progress_percent?: number;
  progress_stage?: string;
  expires_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  file_size_bytes?: number | null;
  manifest?: Record<string, unknown>;
};

type DeletionRequest = {
  id: string;
  status: "awaiting_policy" | "scheduled" | "processing" | "blocked_legal_hold" | "completed" | "cancelled" | "failed";
  requested_at: string;
  policy_version?: string | null;
  scheduled_for?: string | null;
  cancelled_at?: string | null;
};

type Props = { apiBase: string; accessToken: string };

async function apiError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.detail?.message ?? body?.error?.message ?? "Permintaan gagal (" + response.status + ").";
  } catch {
    return "Permintaan gagal (" + response.status + ").";
  }
}

function progressLabel(stage?: string): string {
  const labels: Record<string, string> = {
    claimed: "Worker mengambil job",
    snapshot: "Mengumpulkan data akun",
    compress: "Menyusun arsip",
    upload: "Mengunggah arsip privat",
    publishing: "Menyimpan hasil ekspor",
    completed: "Selesai",
    failed: "Gagal",
  };
  return labels[stage ?? ""] ?? "Menunggu antrean";
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "Dalam antrean",
    running: "Sedang diproses",
    succeeded: "Siap diunduh",
    failed: "Gagal diproses",
    cancelled: "Dibatalkan",
    expired: "Kedaluwarsa",
    awaiting_policy: "Menunggu kebijakan retensi",
    scheduled: "Terjadwal",
    processing: "Sedang diproses",
    blocked_legal_hold: "Ditahan untuk kewajiban hukum",
    completed: "Selesai",
  };
  return labels[status] ?? status;
}

export default function AccountDataLifecyclePanel({ apiBase, accessToken }: Props) {
  const [exports, setExports] = useState<ExportJob[]>([]);
  const [deletions, setDeletions] = useState<DeletionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + accessToken);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, {
      ...init,
      cache: "no-store",
      headers,
    });
    if (!response.ok) throw new Error(await apiError(response));
    return response.status === 204 ? null : response.json();
  }, [accessToken, apiBase]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [exportPayload, deletionPayload] = await Promise.all([
        request("/v1/me/export-requests"),
        request("/v1/me/deletion-requests"),
      ]);
      setExports(Array.isArray(exportPayload?.items) ? exportPayload.items : []);
      setDeletions(Array.isArray(deletionPayload?.items) ? deletionPayload.items : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Data lifecycle akun tidak dapat dimuat.");
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => { void load(); }, [load]);

  async function createExport() {
    setBusy(true); setError(""); setMessage("");
    try {
      const idempotencyKey = globalThis.crypto?.randomUUID?.() ?? ("account-export-" + Date.now());
      const payload = await request("/v1/me/export-requests", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
      });
      setMessage("Permintaan ekspor " + payload.export.id + " berhasil dimasukkan ke antrean.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Permintaan ekspor tidak dapat dibuat.");
    } finally { setBusy(false); }
  }

  async function downloadExport(jobId: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = await request("/v1/me/export-requests/" + encodeURIComponent(jobId) + "/download");
      if (typeof payload?.download_url !== "string" || !payload.download_url) throw new Error("Tautan unduhan tidak tersedia.");
      window.location.assign(payload.download_url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unduhan tidak dapat dibuka.");
      setBusy(false);
    }
  }

  async function createDeletion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = await request("/v1/me/deletion-requests", {
        method: "POST",
        body: JSON.stringify({ password, confirmation_phrase: confirmation }),
      });
      setPassword(""); setConfirmation("");
      setMessage(payload.message ?? "Permintaan penghapusan akun tercatat.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Permintaan penghapusan akun tidak dapat dicatat.");
    } finally { setBusy(false); }
  }

  async function cancelDeletion(requestId: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await request("/v1/me/deletion-requests/" + encodeURIComponent(requestId) + "/cancel", { method: "POST" });
      setMessage("Permintaan penghapusan dibatalkan; status akun dipulihkan oleh backend.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Permintaan tidak dapat dibatalkan.");
    } finally { setBusy(false); }
  }

  const openDeletion = deletions.find((item) => ["awaiting_policy", "scheduled", "processing", "blocked_legal_hold"].includes(item.status));

  return (
    <section className="panel settings-panel social-panel" aria-labelledby="account-data-title">
      <div className="panel-heading">
        <span className="section-kicker">DATA & KONTROL AKUN</span>
        <h2 id="account-data-title">Ekspor dan penghapusan data</h2>
        <p>Permintaan diproses backend Allpha. Berkas ekspor bersifat privat dan tautan unduhan hanya berlaku sementara.</p>
      </div>

      {error && <p className="notice error" role="alert">{error}</p>}
      {message && <p className="notice success" role="status">{message}</p>}

      <section className="social-interests" aria-labelledby="account-export-title">
        <h3 id="account-export-title">Salinan data akun</h3>
        <p className="muted">Buat arsip data akun Anda. Proses berjalan di antrean; halaman ini tidak menganggap permintaan sebagai file yang sudah selesai.</p>
        <button type="button" className="button-primary" disabled={busy} onClick={() => void createExport()}>
          {busy ? "Memproses…" : "Minta ekspor data"}
        </button>
        {loading ? <p className="muted" role="status">Memuat status ekspor…</p> : exports.length === 0 ? <p className="muted">Belum ada permintaan ekspor.</p> : (
          <div className="consent-history-list">
            {exports.map((item) => (
              <article className="social-row" key={item.id}>
                <div>
                  <strong>{statusLabel(item.status)}</strong>
                  <p className="muted">Diminta: {new Date(item.requested_at).toLocaleString("id-ID")}{item.expires_at ? " · Kedaluwarsa " + new Date(item.expires_at).toLocaleString("id-ID") : ""}</p>
                  {item.status === "running" && <div className="export-progress" aria-live="polite"><small className="muted">{progressLabel(item.progress_stage)} · {item.progress_percent ?? 5}%</small><progress aria-label="Progres ekspor akun" value={item.progress_percent ?? 5} max={100} /></div>}
                  {item.file_size_bytes ? <small className="muted">Ukuran: {Math.ceil(item.file_size_bytes / 1024)} KB</small> : null}
                  {item.error_code ? <small className="notice error">{item.error_code}</small> : null}
                </div>
                {item.status === "succeeded" && <button type="button" className="button-quiet" disabled={busy} onClick={() => void downloadExport(item.id)}>Unduh arsip</button>}
              </article>
            ))}
          </div>
        )}
        <button type="button" className="button-quiet" disabled={loading || busy} onClick={() => void load()}>Muat ulang status</button>
      </section>

      <section className="social-interests" aria-labelledby="account-deletion-title">
        <h3 id="account-deletion-title">Permintaan penghapusan akun</h3>
        <p className="muted">Penghapusan permanen belum dijalankan otomatis. Permintaan akan menunggu kebijakan retensi per kelas data dan pemeriksaan legal-hold yang disetujui.</p>
        {deletions.length > 0 && (
          <div className="consent-history-list">
            {deletions.map((item) => (
              <article className="social-row" key={item.id}>
                <div>
                  <strong>{statusLabel(item.status)}</strong>
                  <p className="muted">Diminta: {new Date(item.requested_at).toLocaleString("id-ID")}</p>
                  {item.policy_version && <small className="muted">Kebijakan: {item.policy_version}</small>}
                </div>
                {item.status === "awaiting_policy" && <button type="button" className="button-quiet" disabled={busy} onClick={() => void cancelDeletion(item.id)}>Batalkan</button>}
              </article>
            ))}
          </div>
        )}
        {openDeletion ? <p className="notice">Sudah ada permintaan aktif. Batalkan permintaan tersebut sebelum mengajukan ulang.</p> : (
          <form className="settings-layout" onSubmit={createDeletion}>
            <label>Kata sandi saat ini
              <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={1} maxLength={256} required />
            </label>
            <label>Ketik persis: HAPUS AKUN ALLPHA SAYA
              <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="off" required />
            </label>
            <button type="submit" className="button-danger" disabled={busy || confirmation !== "HAPUS AKUN ALLPHA SAYA" || !password}>
              {busy ? "Memproses…" : "Ajukan penghapusan akun"}
            </button>
          </form>
        )}
      </section>
    </section>
  );
}
