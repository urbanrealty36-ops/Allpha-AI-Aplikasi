import fs from "node:fs";
import path from "node:path";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { findInvalidMeshoptFallbackBuffers } from "../../../tools/3d-assets/meshopt-fallback-compat.mjs";

const file = process.argv[2];
if (!file) throw new Error("Usage: node scripts/spatial-gltfloader-parse.mjs <avatar.glb>");
const raw = fs.readFileSync(file);
if (raw.length < 20 || raw.toString("ascii", 0, 4) !== "glTF") throw new Error("invalid GLB magic/header");
const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
if (view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== raw.length) throw new Error("invalid GLB version/declared length");

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
const invalidFallbacks = findInvalidMeshoptFallbackBuffers(json);
if (invalidFallbacks.length) throw new Error(`invalid Meshopt fallback contract: ${JSON.stringify(invalidFallbacks)}`);
if (!(json.extensionsRequired ?? []).includes("EXT_meshopt_compression")) {
  throw new Error("avatar must require EXT_meshopt_compression when fallback bytes are omitted");
}

// This headless parse removes only material/image references in an in-memory copy.
// Geometry, accessors, skins, nodes, and Meshopt payload bytes remain from the real GLB.
// Full texture/material and GPU visual acceptance is deliberately a separate gate.
const parseJson = structuredClone(json);
parseJson.materials = [];
parseJson.textures = [];
parseJson.images = [];
for (const mesh of parseJson.meshes ?? []) {
  for (const primitive of mesh.primitives ?? []) delete primitive.material;
}
parseJson.extensionsUsed = (parseJson.extensionsUsed ?? []).filter((name) => name !== "EXT_texture_webp");
parseJson.extensionsRequired = (parseJson.extensionsRequired ?? []).filter((name) => name !== "EXT_texture_webp");
const jsonBytes = Buffer.from(JSON.stringify(parseJson), "utf8");
const jsonPadding = Buffer.alloc((4 - (jsonBytes.length % 4)) % 4, 0x20);
const paddedJson = Buffer.concat([jsonBytes, jsonPadding]);
const binChunk = Buffer.from(bin);
const jsonHeader = Buffer.alloc(8);
jsonHeader.writeUInt32LE(paddedJson.length, 0);
jsonHeader.write("JSON", 4, 4, "ascii");
const binHeader = Buffer.alloc(8);
binHeader.writeUInt32LE(binChunk.length, 0);
binHeader.write("BIN\0", 4, 4, "ascii");
const chunks = Buffer.concat([jsonHeader, paddedJson, binHeader, binChunk]);
const header = Buffer.alloc(12);
header.write("glTF", 0, 4, "ascii");
header.writeUInt32LE(2, 4);
header.writeUInt32LE(12 + chunks.length, 8);
const testBytes = Buffer.concat([header, chunks]);
const arrayBuffer = testBytes.buffer.slice(testBytes.byteOffset, testBytes.byteOffset + testBytes.byteLength);

await MeshoptDecoder.ready;
const loader = new GLTFLoader();
loader.setMeshoptDecoder(MeshoptDecoder);
const gltf = await new Promise((resolve, reject) => {
  loader.parse(arrayBuffer, "", resolve, reject);
});
const meshes = [];
gltf.scene.traverse((node) => {
  if (node.isMesh) meshes.push(node);
});
const skinnedMeshes = meshes.filter((node) => node.isSkinnedMesh);
const skeletonBones = new Set(skinnedMeshes.flatMap((node) => node.skeleton?.bones ?? []));
const positionAttributeCount = meshes.reduce((sum, node) => sum + (node.geometry.attributes.position?.count ?? 0), 0);
const geometryIndexCount = meshes.reduce((sum, node) => sum + (node.geometry.index?.count ?? 0), 0);
if (!meshes.length) throw new Error("GLTFLoader parsed no mesh nodes");
if (!skinnedMeshes.length) throw new Error("GLTFLoader parsed no skinned meshes in avatar fixture");
if (!positionAttributeCount) throw new Error("GLTFLoader parsed no POSITION geometry attributes");
if (!skeletonBones.size) throw new Error("GLTFLoader parsed no skeleton bones");
const report = {
  asset: path.basename(file),
  originalBytes: raw.length,
  loader: "Three.js GLTFLoader + bundled MeshoptDecoder",
  parseResult: "passed",
  meshCount: meshes.length,
  skinnedMeshCount: skinnedMeshes.length,
  skeletonBoneCount: skeletonBones.size,
  animationClipCount: gltf.animations.length,
  geometryAttributeNames: [...new Set(meshes.flatMap((node) => Object.keys(node.geometry.attributes)))].sort(),
  positionAttributeCount,
  geometryIndexCount,
  textureMaterialHandling: "stripped from in-memory test copy; not accepted as texture/render proof",
  sourceBytesMutated: false
};
const outDir = path.join(process.cwd(), ".artifacts", "gltfloader-parse");
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, `${path.basename(file, ".glb")}.json`), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
