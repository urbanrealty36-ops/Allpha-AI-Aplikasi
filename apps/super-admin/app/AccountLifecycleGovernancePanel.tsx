"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Props = { apiBase: string; getAccessToken: () => Promise<string> };
type RetentionPolicy = {
  id: string; data_class: string; retention_days: number; policy_version: string;
  legal_basis: string; approved_by: string; approved_at: string; active: boolean;
};
type LegalHold = {
  id: string; subject_ref: string; reference_code: string; reason_code: string;
  active: boolean; created_at: string; released_at?: string | null;
};
type DeletionRequest = {
  id: string; subject_ref: string; status: string; policy_version?: string | null;
  requested_at: string; scheduled_for?: string | null; error_code?: string | null;
};

export default function AccountLifecycleGovernancePanel({ apiBase, getAccessToken }: Props) {
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [holds, setHolds] = useState<LegalHold[]>([]);
  const [requests, setRequests] = useState<DeletionRequest[]>([]);
  const [dataClass, setDataClass] = useState("");
  const [retentionDays, setRetentionDays] = useState("");
  const [policyVersion, setPolicyVersion] = useState("");
  const [legalBasis, setLegalBasis] = useState("");
  const [subjectRef, setSubjectRef] = useState("");
  const [referenceCode, setReferenceCode] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [releaseReason, setReleaseReason] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const token = await getAccessToken();
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + token);
    headers.set("Accept", "application/json");
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) {
      let message = "Permintaan governance gagal (HTTP " + response.status + ").";
      try {
        const body = await response.json();
        message = body?.detail?.message ?? body?.error?.message ?? message;
      } catch { /* keep bounded HTTP fallback */ }
      throw new Error(message);
    }
    return response.status === 204 ? null : response.json();
  }, [apiBase, getAccessToken]);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const query = statusFilter ? "?status=" + encodeURIComponent(statusFilter) : "";
      const [policyPayload, holdPayload, requestPayload] = await Promise.all([
        request("/v1/admin/account-lifecycle/retention-policies"),
        request("/v1/admin/account-lifecycle/legal-holds"),
        request("/v1/admin/account-lifecycle/deletion-requests" + query),
      ]);
      setPolicies(Array.isArray(policyPayload?.items) ? policyPayload.items : []);
      setHolds(Array.isArray(holdPayload?.items) ? holdPayload.items : []);
      setRequests(Array.isArray(requestPayload?.items) ? requestPayload.items : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Governance lifecycle tidak dapat dimuat.");
    } finally { setLoading(false); }
  }, [request, statusFilter]);

  useEffect(() => { void load(); }, [load]);

  async function createPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await request("/v1/admin/account-lifecycle/retention-policies", {
        method: "POST",
        body: JSON.stringify({
          data_class: dataClass.trim(),
          retention_days: Number(retentionDays),
          policy_version: policyVersion.trim(),
          legal_basis: legalBasis.trim(),
        }),
      });
      setDataClass(""); setRetentionDays(""); setPolicyVersion(""); setLegalBasis("");
      setNotice("Kebijakan tersimpan sebagai nonaktif. Aktivasi harus dilakukan secara eksplisit.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Kebijakan tidak dapat dibuat."); }
    finally { setBusy(false); }
  }

  async function setPolicyActive(policy: RetentionPolicy, active: boolean) {
    setBusy(true); setError(""); setNotice("");
    try {
      await request("/v1/admin/account-lifecycle/retention-policies/" + encodeURIComponent(policy.id) + (active ? "/activate" : "/deactivate"), { method: "POST" });
      setNotice("Status kebijakan " + policy.data_class + " diperbarui melalui transaksi backend.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Status kebijakan tidak dapat diubah."); }
    finally { setBusy(false); }
  }

  async function createHold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      await request("/v1/admin/account-lifecycle/legal-holds", {
        method: "POST",
        body: JSON.stringify({ subject_ref: subjectRef.trim().toLowerCase(), reference_code: referenceCode.trim(), reason_code: reasonCode.trim() }),
      });
      setSubjectRef(""); setReferenceCode(""); setReasonCode("");
      setNotice("Legal hold tercatat dan aktif.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Legal hold tidak dapat dibuat."); }
    finally { setBusy(false); }
  }

  async function releaseHold(hold: LegalHold) {
    if (releaseReason.trim().length < 8) {
      setError("Alasan pelepasan legal hold minimal 8 karakter.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      await request("/v1/admin/account-lifecycle/legal-holds/" + encodeURIComponent(hold.id) + "/release", {
        method: "POST", body: JSON.stringify({ reason: releaseReason.trim() }),
      });
      setReleaseReason("");
      setNotice("Legal hold dilepas dan keputusan dicatat di audit operator.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Legal hold tidak dapat dilepas."); }
    finally { setBusy(false); }
  }

  return (
    <section className="panel" id="account-lifecycle">
      <header className="panelHead">
        <div><h2>Account Lifecycle Governance</h2><p>Kelola referensi kebijakan retensi dan legal hold. Tidak ada periode default dan tidak ada tombol penghapusan permanen.</p></div>
        <span className="pill warning">EXPLICIT POLICY ONLY</span>
      </header>
      {error && <p className="notice errorNotice" role="alert">{error}</p>}
      {notice && <p className="notice successNotice" role="status">{notice}</p>}

      <section className="panel">
        <header className="panelHead"><div><h3>Kebijakan retensi per kelas data</h3><p>Nilai dan dasar hukum harus berasal dari keputusan yang disahkan. Kebijakan baru selalu nonaktif sampai operator mengaktifkannya.</p></div></header>
        <form className="grantForm" onSubmit={createPolicy}>
          <label>Data class<input value={dataClass} onChange={event => setDataClass(event.target.value)} pattern="[a-z][a-z0-9_]{1,63}" maxLength={64} required placeholder="contoh: social_content" /></label>
          <label>Retention days<input type="number" min={0} max={36500} step={1} value={retentionDays} onChange={event => setRetentionDays(event.target.value)} required /></label>
          <label>Policy version<input value={policyVersion} onChange={event => setPolicyVersion(event.target.value)} maxLength={40} required placeholder="referensi versi resmi" /></label>
          <label>Legal basis<textarea value={legalBasis} onChange={event => setLegalBasis(event.target.value)} minLength={8} maxLength={500} required placeholder="Dasar hukum yang disetujui, bukan teks otomatis." /></label>
          <button type="submit" disabled={busy || !dataClass.trim() || !retentionDays || !policyVersion.trim() || legalBasis.trim().length < 8}>Simpan kebijakan nonaktif</button>
        </form>
        <div className="tableWrap"><table><thead><tr><th>Data class</th><th>Durasi</th><th>Versi / dasar</th><th>Status</th><th>Aksi</th></tr></thead><tbody>
          {policies.map(policy => <tr key={policy.id}><td><strong>{policy.data_class}</strong></td><td>{policy.retention_days} hari</td><td>{policy.policy_version}<br/><small>{policy.legal_basis}</small></td><td><span className={"pill " + (policy.active ? "online" : "warning")}>{policy.active ? "active" : "inactive"}</span></td><td>{policy.active ? <button className="secondaryButton" disabled={busy} onClick={() => void setPolicyActive(policy, false)}>Nonaktifkan</button> : <button disabled={busy} onClick={() => void setPolicyActive(policy, true)}>Aktifkan</button>}</td></tr>)}
          {!policies.length && <tr><td colSpan={5} className="emptyCell">{loading ? "Memuat kebijakan…" : "Belum ada kebijakan. Tidak ada periode retensi yang diasumsikan."}</td></tr>}
        </tbody></table></div>
      </section>

      <section className="panel">
        <header className="panelHead"><div><h3>Legal holds</h3><p>Setiap hold membutuhkan reference code dan reason code dari proses legal yang berwenang.</p></div></header>
        <form className="grantForm" onSubmit={createHold}>
          <label>Subject reference (UUID)<input value={subjectRef} onChange={event => setSubjectRef(event.target.value)} required pattern="[0-9a-fA-F-]{36}" placeholder="UUID subjek akun" /></label>
          <label>Reference code<input value={referenceCode} onChange={event => setReferenceCode(event.target.value)} required maxLength={120} /></label>
          <label>Reason code<input value={reasonCode} onChange={event => setReasonCode(event.target.value)} required maxLength={80} pattern="[a-z][a-z0-9._-]{2,79}" /></label>
          <button type="submit" disabled={busy || !subjectRef.trim() || !referenceCode.trim() || !reasonCode.trim()}>Catat legal hold</button>
        </form>
        <label className="reviewReason">Alasan pelepasan legal hold<input value={releaseReason} onChange={event => setReleaseReason(event.target.value)} minLength={8} maxLength={500} /></label>
        <div className="tableWrap"><table><thead><tr><th>Subject</th><th>Referensi</th><th>Reason</th><th>Status</th><th>Aksi</th></tr></thead><tbody>
          {holds.map(hold => <tr key={hold.id}><td><code>{hold.subject_ref}</code></td><td>{hold.reference_code}</td><td>{hold.reason_code}</td><td><span className={"pill " + (hold.active ? "warning" : "online")}>{hold.active ? "active" : "released"}</span></td><td>{hold.active && <button className="secondaryButton" disabled={busy || releaseReason.trim().length < 8} onClick={() => void releaseHold(hold)}>Lepas hold</button>}</td></tr>)}
          {!holds.length && <tr><td colSpan={5} className="emptyCell">{loading ? "Memuat legal hold…" : "Tidak ada legal hold."}</td></tr>}
        </tbody></table></div>
      </section>

      <section className="panel">
        <header className="panelHead"><div><h3>Permintaan penghapusan akun</h3><p>Daftar permintaan dan status fail-closed. Penjadwalan/penghapusan tidak tersedia selama seluruh kelas data belum memiliki kebijakan aktif dan legal hold belum diperiksa.</p></div>
          <select aria-label="Filter status penghapusan" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">Semua status</option><option value="awaiting_policy">awaiting_policy</option><option value="scheduled">scheduled</option><option value="processing">processing</option><option value="blocked_legal_hold">blocked_legal_hold</option><option value="completed">completed</option><option value="cancelled">cancelled</option><option value="failed">failed</option></select>
        </header>
        <div className="tableWrap"><table><thead><tr><th>Request</th><th>Subject</th><th>Status</th><th>Diminta</th><th>Terjadwal</th><th>Error</th></tr></thead><tbody>
          {requests.map(item => <tr key={item.id}><td><code>{item.id}</code></td><td><code>{item.subject_ref}</code></td><td><span className="pill warning">{item.status}</span></td><td>{new Date(item.requested_at).toLocaleString("id-ID")}</td><td>{item.scheduled_for ? new Date(item.scheduled_for).toLocaleString("id-ID") : "—"}</td><td>{item.error_code || "—"}</td></tr>)}
          {!requests.length && <tr><td colSpan={6} className="emptyCell">{loading ? "Memuat permintaan…" : "Tidak ada permintaan pada filter ini."}</td></tr>}
        </tbody></table></div>
      </section>
      <div className="panelActions"><button className="secondaryButton" disabled={loading || busy} onClick={() => void load()}>Refresh governance data</button><span className="muted">Penghapusan permanen tetap dikunci oleh backend.</span></div>
    </section>
  );
}
