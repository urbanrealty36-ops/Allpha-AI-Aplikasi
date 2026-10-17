import fs from "node:fs";
import path from "node:path";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";

const file = process.argv[2];
if (!file) throw new Error("Usage: node scripts/spatial-glb-regression.mjs <fixture.glb>");
const raw = fs.readFileSync(file);
const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
if (raw.length < 20 || raw.toString("ascii", 0, 4) !== "glTF") throw new Error("invalid GLB magic/header");
if (view.getUint32(4, true) !== 2) throw new Error("GLB version must be 2");
if (view.getUint32(8, true) !== raw.length) throw new Error("GLB declared length mismatch");

let offset = 12, json = null, bin = null;
while (offset < raw.length) {
  if (offset + 8 > raw.length) throw new Error("truncated GLB chunk header");
  const len = view.getUint32(offset, true);
  const kind = raw.toString("ascii", offset + 4, offset + 8);
  const start = offset + 8, end = start + len;
  if (len % 4 || end > raw.length) throw new Error("invalid GLB chunk bounds");
  if (kind === "JSON") {
    if (json) throw new Error("duplicate JSON chunk");
    json = JSON.parse(raw.toString("utf8", start, end).replace(/[\u0000 \t\r\n]+$/u, ""));
  } else if (kind === "BIN\u0000") {
    bin = raw.subarray(start, end);
  }
  offset = end;
}
if (!json || !bin) throw new Error("fixture requires JSON and BIN chunks");
const declaredExts = [...(json.extensionsUsed ?? []), ...(json.extensionsRequired ?? [])];
const buffers = json.buffers ?? [];
const unresolvedBaseBuffers = [...new Set((json.bufferViews ?? [])
  .map((bufferView) => bufferView.buffer ?? 0)
  .filter((index) => !Number.isInteger(index) || index < 0 || index >= buffers.length
    || (index > 0 && !buffers[index]?.uri)))];
if (unresolvedBaseBuffers.length) {
  throw new Error(`base buffer(s) ${unresolvedBaseBuffers.join(", ")} are missing resolvable URI data; Meshopt byte decoding alone cannot prove GLTFLoader compatibility`);
}
if (!declaredExts.includes("EXT_meshopt_compression")) throw new Error("EXT_meshopt_compression is absent");
if (!declaredExts.includes("EXT_texture_webp")) throw new Error("EXT_texture_webp is absent");

await MeshoptDecoder.ready;
const decoded = [];
for (const [index, bufferView] of (json.bufferViews ?? []).entries()) {
  const ext = bufferView.extensions?.EXT_meshopt_compression;
  if (!ext) continue;
  if (ext.buffer !== 0) throw new Error(\`bufferView \${index}: only embedded GLB buffer 0 is supported by fixture regression\`);
  const start = Number(ext.byteOffset ?? 0), end = start + Number(ext.byteLength);
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end > bin.length || end <= start) {
    throw new Error(\`bufferView \${index}: compressed byte range out of bounds\`);
  }
  const count = Number(ext.count), stride = Number(ext.byteStride);
  if (!Number.isSafeInteger(count) || !Number.isSafeInteger(stride) || count <= 0 || stride <= 0) {
    throw new Error(\`bufferView \${index}: invalid count/stride\`);
  }
  const mode = ext.mode;
  const filter = ext.filter ?? "NONE";
  const output = new Uint8Array(count * stride);
  await MeshoptDecoder.decodeGltfBuffer(output, count, stride, bin.subarray(start, end), mode, filter);
  decoded.push({ bufferView: index, mode, filter, count, stride, compressedBytes: end - start, decodedBytes: output.byteLength });
}
if (!decoded.length) throw new Error("no EXT_meshopt_compression bufferViews were decoded");
const primitives = (json.meshes ?? []).flatMap((mesh) => mesh.primitives ?? []);
const accessorCounts = (json.accessors ?? []).map((a) => a.count).filter(Number.isFinite);
const report = {
  platformHarness: path.resolve(process.cwd()),
  fileBytes: raw.length,
  extensions: declaredExts,
  compressedBufferViews: decoded.length,
  decodedBufferViews: decoded.length,
  decodedBytes: decoded.reduce((sum, x) => sum + x.decodedBytes, 0),
  meshCount: (json.meshes ?? []).length,
  primitiveCount: primitives.length,
  accessorCount: (json.accessors ?? []).length,
  accessorElementCount: accessorCounts.reduce((sum, n) => sum + n, 0),
  materialCount: (json.materials ?? []).length,
  textureCount: (json.textures ?? []).length,
  imageCount: (json.images ?? []).length,
  skinCount: (json.skins ?? []).length,
  animationCount: (json.animations ?? []).length,
  decoded,
  note: "This is a real meshopt byte-decoding regression, not a GPU render or texture-decode acceptance test."
};
const outDir = path.join(process.cwd(), ".artifacts");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "spatial-regression.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
