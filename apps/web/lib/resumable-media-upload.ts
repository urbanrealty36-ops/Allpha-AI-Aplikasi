import { getBrowserSupabasePublishableKey } from "./supabase";

export type ResumableMediaInit = {
  item: { id: string };
  already_uploaded: boolean;
  tus_endpoint?: string;
  upload_token?: string;
  upload_metadata?: Record<string, string>;
  chunk_size_bytes?: number;
};

export type AuthenticatedMediaRequest = (path: string, init?: RequestInit) => Promise<unknown>;

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`;
  } catch {
    return `Permintaan gagal (HTTP ${response.status}).`;
  }
}

function encodeTusMetadata(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/** Canonical browser upload flow: signed TUS session -> offset-fenced chunks -> API completion. */
export async function uploadContentMediaWithTus(
  request: AuthenticatedMediaRequest,
  contentId: string,
  file: File,
  idempotencyKey: string,
  onProgress: (percent: number) => void,
): Promise<{ id: string }> {
  if (!Number.isSafeInteger(file.size) || file.size <= 0) {
    throw new Error("Ukuran file media tidak valid untuk upload resumable.");
  }
  const initialized = await request(`/v1/content/${encodeURIComponent(contentId)}/media/resumable`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ filename: file.name, media_type: file.type, size_bytes: file.size }),
  });
  const init = initialized as ResumableMediaInit;
  if (init.already_uploaded) return init.item;
  if (!init.item?.id || !init.tus_endpoint || !init.upload_token || !init.upload_metadata) {
    throw new Error("Kontrak upload resumable dari server tidak lengkap.");
  }
  const apiKey = getBrowserSupabasePublishableKey();
  if (!apiKey) throw new Error("Konfigurasi Storage publik belum tersedia pada aplikasi.");
  const headers = {
    "Tus-Resumable": "1.0.0",
    apikey: apiKey,
    "x-signature": init.upload_token,
  };
  const sessionKey = `allpha:content:tus:${contentId}:${init.item.id}`;
  let uploadUrl: string | null = null;
  try { uploadUrl = sessionStorage.getItem(sessionKey); } catch { /* Current-page chunking still works without tab persistence. */ }

  const readOffset = async (target: string): Promise<number> => {
    const response = await fetch(target, { method: "HEAD", headers, cache: "no-store" });
    if (response.status === 404 || response.status === 410) return -1;
    if (!response.ok) throw new Error(await responseError(response));
    const offset = Number(response.headers.get("Upload-Offset"));
    if (!Number.isSafeInteger(offset) || offset < 0 || offset > file.size) {
      throw new Error("Offset upload resumable dari Storage tidak valid.");
    }
    return offset;
  };

  let offset = uploadUrl ? await readOffset(uploadUrl) : -1;
  if (offset < 0) {
    try { sessionStorage.removeItem(sessionKey); } catch { /* Ignore unavailable session storage. */ }
    const metadata = Object.entries(init.upload_metadata)
      .map(([key, value]) => key + " " + encodeTusMetadata(value))
      .join(",");
    const created = await fetch(init.tus_endpoint, {
      method: "POST",
      headers: { ...headers, "Upload-Length": String(file.size), "Upload-Metadata": metadata },
      cache: "no-store",
    });
    if (created.status === 409) {
      const completed = await request(
        `/v1/content/${encodeURIComponent(contentId)}/media/${encodeURIComponent(init.item.id)}/complete`,
        { method: "POST" },
      ) as { item: { id: string } };
      return completed.item;
    }
    if (created.status !== 201) throw new Error(await responseError(created));
    const location = created.headers.get("Location");
    if (!location) throw new Error("Storage tidak mengembalikan URL sesi resumable.");
    uploadUrl = new URL(location, init.tus_endpoint).toString();
    try { sessionStorage.setItem(sessionKey, uploadUrl); } catch { /* Resume remains available while this page is open. */ }
    offset = 0;
  }

  onProgress(Math.min(100, Math.floor((offset / file.size) * 100)));
  const chunkSize = init.chunk_size_bytes || 6 * 1024 * 1024;
  while (offset < file.size) {
    const response = await fetch(uploadUrl!, {
      method: "PATCH",
      headers: {
        ...headers,
        "Upload-Offset": String(offset),
        "Content-Type": "application/offset+octet-stream",
      },
      body: file.slice(offset, Math.min(file.size, offset + chunkSize)),
      cache: "no-store",
    });
    if (response.status === 409) {
      const refreshed = await readOffset(uploadUrl!);
      if (refreshed <= offset) throw new Error("Sesi upload berubah tanpa kemajuan byte; lanjutkan kembali setelah memuat ulang status.");
      offset = refreshed;
      continue;
    }
    if (response.status !== 204) throw new Error(await responseError(response));
    let nextOffset = Number(response.headers.get("Upload-Offset"));
    if (!Number.isSafeInteger(nextOffset) || nextOffset <= offset || nextOffset > file.size) {
      nextOffset = await readOffset(uploadUrl!);
    }
    if (nextOffset <= offset) throw new Error("Storage belum mengonfirmasi kemajuan chunk upload.");
    offset = nextOffset;
    onProgress(Math.min(100, Math.floor((offset / file.size) * 100)));
  }

  if (await readOffset(uploadUrl!) !== file.size) {
    throw new Error("Storage belum mengonfirmasi seluruh byte upload.");
  }
  onProgress(100);
  const completed = await request(
    `/v1/content/${encodeURIComponent(contentId)}/media/${encodeURIComponent(init.item.id)}/complete`,
    { method: "POST" },
  ) as { item: { id: string } };
  try { sessionStorage.removeItem(sessionKey); } catch { /* Ignore unavailable session storage. */ }
  return completed.item;
}
