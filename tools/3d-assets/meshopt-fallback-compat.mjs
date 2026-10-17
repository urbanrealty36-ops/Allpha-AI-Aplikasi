/** Return URI-less nonzero buffers that violate the EXT_meshopt_compression fallback contract. */
export function findInvalidMeshoptFallbackBuffers(json) {
  const buffers = json.buffers ?? [];
  const views = json.bufferViews ?? [];
  const required = new Set(json.extensionsRequired ?? []);
  const invalid = [];
  for (let index = 1; index < buffers.length; index += 1) {
    const buffer = buffers[index];
    if (!buffer || buffer.uri) continue;
    const refs = views.filter((view) => (view.buffer ?? 0) === index);
    const compressedSourceRefs = views.filter(
      (view) => view.extensions?.EXT_meshopt_compression?.buffer === index
    );
    const reasons = [];
    if (buffer.extensions?.EXT_meshopt_compression?.fallback !== true) reasons.push("fallback_flag_missing");
    if (!required.has("EXT_meshopt_compression")) reasons.push("meshopt_extension_not_required");
    if (!refs.length) reasons.push("fallback_buffer_unreferenced");
    if (refs.some((view) => !view.extensions?.EXT_meshopt_compression)) {
      reasons.push("fallback_view_without_meshopt_extension");
    }
    if (compressedSourceRefs.length) reasons.push("fallback_used_as_compressed_source");
    const maxEnd = refs.reduce((max, view) => {
      const offset = view.byteOffset ?? 0;
      const length = view.byteLength;
      return Number.isSafeInteger(offset) && Number.isSafeInteger(length) && length >= 0
        ? Math.max(max, offset + length)
        : Number.POSITIVE_INFINITY;
    }, 0);
    if (!Number.isSafeInteger(buffer.byteLength) || buffer.byteLength < maxEnd) {
      reasons.push("fallback_byte_length_too_short");
    }
    if (reasons.length) invalid.push({ index, reasons });
  }
  return invalid;
}
