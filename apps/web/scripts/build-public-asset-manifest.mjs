import { createHash } from "node:crypto";
import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const publicDirectory = path.resolve(scriptDirectory, "../public");
const outputPath = path.join(publicDirectory, "asset-manifest.json");

async function collectFiles(directory, prefix = "") {
  const entries = await readdir(directory, { withFileTypes: true });
  entries.sort((left, right) => left.name.localeCompare(right.name));
  const assets = [];

  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);
    const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      assets.push(...await collectFiles(absolutePath, relativePath));
      continue;
    }
    if (!entry.isFile() || relativePath === "asset-manifest.json") continue;
    if (relativePath.toLowerCase().endsWith(".md")) {
      throw new Error(`Refusing to publish a Markdown document from public/: ${relativePath}`);
    }
    const bytes = await readFile(absolutePath);
    assets.push({
      path: `/${relativePath.split(path.sep).join("/")}`,
      bytes: bytes.byteLength,
      sha256: createHash("sha256").update(bytes).digest("hex"),
    });
  }
  return assets;
}

const manifest = {
  schema_version: 1,
  assets: await collectFiles(publicDirectory),
};
manifest.assets.sort((left, right) => left.path.localeCompare(right.path));
await writeFile(outputPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`Generated public asset manifest for ${manifest.assets.length} files.`);
