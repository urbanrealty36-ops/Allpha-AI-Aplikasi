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
  mediaType = file.type,
): Promise<{ id: string }> {
  if (!Number.isSafeInteger(file.size) || file.size <= 0) {
    throw new Error("Ukuran file media tidak valid untuk upload resumable.");
  }
  const initialized = await request(`/v1/content/${encodeURIComponent(contentId)}/media/resumable`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ filename: file.name, media_type: mediaType, size_bytes: file.size }),
  });
  const init = initialized as ResumableMediaInit;
  if (!init.item?.id) throw new Error("API tidak mengembalikan identitas media untuk upload resumable.");
  const sessionKey = `allpha:content:tus:${contentId}:${init.item.id}`;
  if (init.already_uploaded) {
    try { sessionStorage.removeItem(sessionKey); } catch { /* Ignore unavailable session storage. */ }
    return init.item;
  }
  if (!init.tus_endpoint || !init.upload_token || !init.upload_metadata) {
    throw new Error("Kontrak upload resumable dari server tidak lengkap.");
  }
  const apiKey = getBrowserSupabasePublishableKey();
  if (!apiKey) throw new Error("Konfigurasi Storage publik belum tersedia pada aplikasi.");
  const headers = {
    "Tus-Resumable": "1.0.0",
    apikey: apiKey,
    "x-signature": init.upload_token,
  };
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
      try { sessionStorage.removeItem(sessionKey); } catch { /* Ignore unavailable session storage. */ }
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


/**
 * Canonical client entry point. Cloudinary rollout is opt-in and remains disabled
 * until the production registry migration, scanner and worker readiness gates pass.
 */
export async function uploadContentMedia(
  request: AuthenticatedMediaRequest,
  contentId: string,
  file: File,
  idempotencyKey: string,
  onProgress: (percent: number) => void,
  mediaType = file.type,
): Promise<{ id: string }> {
  const cloudinaryEligible = mediaType.startsWith("image/")
    || mediaType.startsWith("video/")
    || mediaType.startsWith("audio/");
  if (process.env.NEXT_PUBLIC_ALLPHA_CLOUDINARY_MEDIA_ENABLED === "true" && cloudinaryEligible) {
    return uploadContentMediaWithCloudinary(request, contentId, file, idempotencyKey, onProgress, mediaType);
  }
  return uploadContentMediaWithTus(request, contentId, file, idempotencyKey, onProgress, mediaType);
}


export type CloudinaryUploadIntent = {
  item: { id: string; status: string };
  upload: {
    upload_url: string;
    resource_type: string;
    delivery_type: string;
    public_id: string;
    params: Record<string, string | number | boolean>;
    expires_at: number;
  };
  expires_in_seconds: number;
};

async function uploadDirectToCloudinary(
  file: File,
  intent: CloudinaryUploadIntent,
  onProgress: (percent: number) => void,
): Promise<void> {
  if (!intent.upload?.upload_url || !intent.upload.params || !intent.upload.public_id) {
    throw new Error("Kontrak upload Cloudinary dari API tidak lengkap.");
  }
  if (["uploaded", "processing", "ready"].includes(intent.item.status)) {
    onProgress(95);
    return;
  }
  if (intent.upload.expires_at <= Math.floor(Date.now() / 1000)) {
    throw new Error("Intent upload Cloudinary sudah kedaluwarsa. Mulai ulang upload media.");
  }
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(intent.upload.params)) form.append(key, String(value));
  const result = await new Promise<{ status: number; body: string }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", intent.upload.upload_url);
    xhr.timeout = 180000;
    xhr.upload.onprogress = event => {
      if (event.lengthComputable && event.total > 0) onProgress(Math.min(90, Math.floor(event.loaded / event.total * 90)));
    };
    xhr.onload = () => resolve({ status: xhr.status, body: xhr.responseText || "" });
    xhr.onerror = () => reject(new Error("Koneksi ke Cloudinary terputus. Upload dapat dicoba kembali."));
    xhr.ontimeout = () => reject(new Error("Upload Cloudinary melewati batas waktu."));
    xhr.send(form);
  });
  if (result.status >= 200 && result.status < 300) {
    let asset: Record<string, unknown>;
    try { asset = JSON.parse(result.body) as Record<string, unknown>; }
    catch { throw new Error("Respons upload Cloudinary tidak valid."); }
    if (asset.public_id !== intent.upload.public_id
      || asset.resource_type !== intent.upload.resource_type
      || asset.type !== "authenticated"
      || Number(asset.bytes) !== file.size) {
      throw new Error("Identitas asset Cloudinary tidak sesuai dengan upload intent.");
    }
  } else {
    let providerMessage = "";
    try { providerMessage = String((JSON.parse(result.body) as { error?: { message?: string } }).error?.message || ""); }
    catch { /* Preserve the provider HTTP status. */ }
    const duplicate = result.status === 409 || /already exists|already uploaded/i.test(providerMessage);
    if (!duplicate) throw new Error(providerMessage || ("Cloudinary menolak upload (HTTP " + result.status + ")."));
  }
  onProgress(95);
}


/** Direct authenticated Cloudinary upload; API reserves and verifies every asset. */
export async function uploadContentMediaWithCloudinary(
  request: AuthenticatedMediaRequest,
  contentId: string,
  file: File,
  idempotencyKey: string,
  onProgress: (percent: number) => void,
  mediaType = file.type,
): Promise<{ id: string }> {
  if (!Number.isSafeInteger(file.size) || file.size <= 0) throw new Error("Ukuran file media tidak valid.");
  if (!mediaType) throw new Error("Tipe MIME file wajib tersedia.");
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const sha256 = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  const raw = await request("/v1/media/upload-intents", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify({ content_id: contentId, filename: file.name, media_type: mediaType, size_bytes: file.size, sha256 }),
  });
  const intent = raw as CloudinaryUploadIntent;
  if (!intent.item?.id || !intent.upload?.upload_url || !intent.upload?.params) {
    throw new Error("Kontrak upload Cloudinary dari API tidak lengkap.");
  }
  await uploadDirectToCloudinary(file, intent, onProgress);
  const completed = await request("/v1/media/complete", {
    method: "POST",
    body: JSON.stringify({ media_id: intent.item.id }),
  }) as { item?: { id?: string } };
  if (!completed.item?.id) throw new Error("API belum mengonfirmasi penyelesaian upload media.");
  onProgress(100);
  return { id: completed.item.id };
}
