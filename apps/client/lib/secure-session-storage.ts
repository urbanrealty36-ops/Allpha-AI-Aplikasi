export type SecureKeyValueStore = {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
};

const CHUNK_SIZE = 1800;
const MAX_CHUNKS = 30;
const MANIFEST_PREFIX = "v1:";
const DELETED_MANIFEST = "v1:deleted";

function parseManifest(value: string): { generation: string; count: number } | null {
  if (value === DELETED_MANIFEST) return null;
  if (!value.startsWith(MANIFEST_PREFIX)) throw new Error("Manifest sesi native tidak valid.");
  const [, generation, rawCount] = value.split(":");
  const count = Number(rawCount);
  if (!generation || !Number.isInteger(count) || count < 1 || count > MAX_CHUNKS) {
    throw new Error("Manifest sesi native tidak valid.");
  }
  return { generation, count };
}

/**
 * Versioned chunk storage. The manifest is the commit pointer and is only
 * replaced after every chunk is durable, so interrupted writes keep the
 * previous Supabase session readable.
 */
export function createSecureSessionStorage(store: SecureKeyValueStore) {
  const queues = new Map<string, Promise<void>>();

  async function serialize<T>(key: string, operation: () => Promise<T>): Promise<T> {
    const previous = queues.get(key) ?? Promise.resolve();
    let release!: () => void;
    const current = new Promise<void>(resolve => { release = resolve; });
    queues.set(key, previous.then(() => current));
    await previous;
    try {
      return await operation();
    } finally {
      release();
      if (queues.get(key) === current) queues.delete(key);
    }
  }

  async function cleanupGeneration(key: string, generation: string, count: number) {
    await Promise.all(Array.from({ length: count }, (_, index) =>
      store.deleteItemAsync(`${key}:v1:${generation}:${index}`).catch(() => undefined)
    ));
  }

  return {
    async getItem(key: string): Promise<string | null> {
      const manifest = await store.getItemAsync(key + ":manifest");
      if (manifest !== null) {
        const parsed = parseManifest(manifest);
        if (!parsed) return null;
        const chunks = await Promise.all(Array.from({ length: parsed.count }, (_, index) =>
          store.getItemAsync(`${key}:v1:${parsed.generation}:${index}`)
        ));
        if (chunks.some(chunk => chunk === null)) {
          throw new Error("Sesi aman tidak lengkap; data lama tidak akan dipakai sebagai fallback.");
        }
        return (chunks as string[]).join("");
      }

      // Backward-compatible read for sessions written by the previous
      // key:count/key:index format; the next successful write migrates it.
      const legacyCount = Number(await store.getItemAsync(key + ":count") || 0);
      if (legacyCount > 0 && legacyCount <= MAX_CHUNKS) {
        const chunks = await Promise.all(Array.from({ length: legacyCount }, (_, index) =>
          store.getItemAsync(key + ":" + index)
        ));
        return chunks.every(chunk => chunk !== null) ? (chunks as string[]).join("") : null;
      }
      return store.getItemAsync(key);
    },

    async setItem(key: string, value: string): Promise<void> {
      return serialize(key, async () => {
        const previousManifest = await store.getItemAsync(key + ":manifest");
        const previous = previousManifest === null ? null : parseManifest(previousManifest);
        const chunks = value.match(/[\s\S]{1,1800}/g) || [""];
        if (chunks.length > MAX_CHUNKS) {
          throw new Error("Sesi terlalu besar untuk penyimpanan aman perangkat.");
        }
        const generation = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
        let written = 0;
        try {
          for (let index = 0; index < chunks.length; index++) {
            await store.setItemAsync(`${key}:v1:${generation}:${index}`, chunks[index]);
            written++;
          }
          // Single-key pointer update is the commit point. Until this succeeds,
          // getItem continues to resolve the previous complete generation.
          await store.setItemAsync(key + ":manifest", `${MANIFEST_PREFIX}${generation}:${chunks.length}`);
        } catch (error) {
          await cleanupGeneration(key, generation, written);
          throw error;
        }

        if (previous) await cleanupGeneration(key, previous.generation, previous.count);
        const legacyCount = Number(await store.getItemAsync(key + ":count").catch(() => "0") || 0);
        if (legacyCount > 0 && legacyCount <= MAX_CHUNKS) {
          await Promise.all(Array.from({ length: legacyCount }, (_, index) =>
            store.deleteItemAsync(key + ":" + index).catch(() => undefined)
          ));
        }
        await store.deleteItemAsync(key + ":count").catch(() => undefined);
        await store.deleteItemAsync(key).catch(() => undefined);
      });
    },

    async removeItem(key: string): Promise<void> {
      return serialize(key, async () => {
        const manifest = await store.getItemAsync(key + ":manifest");
        const previous = manifest === null ? null : parseManifest(manifest);
        // Tombstone first: a crash during cleanup must never resurrect a session.
        await store.setItemAsync(key + ":manifest", DELETED_MANIFEST);
        if (previous) await cleanupGeneration(key, previous.generation, previous.count);
        const legacyCount = Number(await store.getItemAsync(key + ":count").catch(() => "0") || 0);
        if (legacyCount > 0 && legacyCount <= MAX_CHUNKS) {
          await Promise.all(Array.from({ length: legacyCount }, (_, index) =>
            store.deleteItemAsync(key + ":" + index).catch(() => undefined)
          ));
        }
        await store.deleteItemAsync(key + ":count").catch(() => undefined);
        await store.deleteItemAsync(key).catch(() => undefined);
      });
    }
  };
}
