# Allpha GLB Gate Closure — 2026-10-17

## Decision

**No asset is approved. No Supabase mutation, upload, registry write, or publication was performed.** ENG-P22 and ENG-P23 remain `in_progress`.

## 1. Seventeen quarantined assets

- Per-file record: `quarantine-17-per-asset-rights-visual-review.csv` in the evidence package. Each row records source path/URL, acquired SHA-256/size, GLB metadata, skins/animations, preview reference, cautious visual note, provisional category candidate, and decision.
- Public source repository: https://github.com/ramjigeddam/3d. The public repository listing contains the model files but no LICENSE file is listed in its root. No applicable asset license/permission was found in this pass. All 17 remain **QUARANTINE**.
- All 17 received offline software-rendered, textured triage previews with face decimation. Several models show fragmented surfaces or apparent scale/orientation/material issues. This is not a production PBR renderer and does not qualify as final visual acceptance.
- Preview-supported provisional candidates include human/armored characters, a fox-like creature, house/building, and vehicle props. Unclear/fragmented previews remain UNMAPPED. These are not canonical category assignments.

## 2. 232 VALID avatar files — exact path reconciliation

The upstream `c-frame/valid-avatars-glb/avatars.json` declares 210 model paths: https://github.com/c-frame/valid-avatars-glb/blob/main/avatars.json

- **208 exact path matches** in the acquired set.
- **24 extra `Default` outfit files** not listed in the canonical 210-entry manifest.
- **2 expected canonical paths missing from acquisition:** `avatars/AIAN/AIAN_F_2_Medi.glb` and `avatars/Hispanic/Hispanic_M_3_Util.glb`.

Every acquired row has its own SHA-256 and byte size in the evidence matrix. The 208 path matches are not yet cleared for publication: per-asset source lineage and MIT attribution need to be carried through to the approval record. The 24 extra Default variants remain held because they do not match the canonical manifest.

**Compatibility blocker:** all 232 acquired avatar GLBs declare `EXT_meshopt_compression` and two buffers, including a second buffer without a URI. The local GLTF parser cannot decode these models, so no avatar model renders were produced in this pass. All 232 list skins but declare zero animation clips in their acquired GLB JSON. The canonical Web/Native renderer must be tested with a standards-compliant decoder/asset or the files must be repaired/re-exported before these assets can be accepted.

## 3. Thirteen SourceCityToolkit GLBs / texture provenance

- 13/13 model JSON manifests were parsed.
- **219/219 embedded images were extracted and decoded**, with SHA-256, MIME type, byte size, and dimensions recorded per image.
- The upstream repository declares CC0-1.0 but its README explicitly excludes redistribution of certain Textures.com photographic textures. The extracted atlas contains color/albedo-like maps, normal maps, and packed/utility textures; image appearance alone does not establish source provenance.
- No per-image source attribution was found in the GLB metadata. All 13 models remain **HOLD** pending a texture source map/rights evidence. Full scene/PBR/orientation review remains incomplete.

## 4. Browser E2E and Android/iOS

- Browser E2E against the canonical Allpha renderer: **NOT RUN**. The source-only spatial catalog migration is not applied and the API contract intentionally fails closed until an approved non-production schema and storage bucket are configured. No real published manifest/approved asset version is available for the canonical route.
- Real Android device QA: **NOT RUN**. Real iOS device QA: **NOT RUN**. This execution had no attached physical devices or confirmed non-production device-test target.
- FPS, load-time, memory, error/retry telemetry: **NOT CAPTURED**. Software-rendered previews are not performance telemetry.

## 5. Human approval packet

The evidence bundle contains `human-approval-packet.json` with the required sign-off fields and exclusions. **Zero candidates are ready for human approval** because legal, visual/runtime, and/or device gates remain open. This packet does not approve any asset.

## Evidence bundle contents

- `quarantine-17-per-asset-rights-visual-review.csv`
- `avatar-232-exact-manifest-reconciliation.csv`
- `city-13-per-asset-texture-provenance.csv`
- `city-219-embedded-image-hashes.csv`
- `quarantine-17-rendered-contact-sheet.jpg`
- `city-13-embedded-textures-contact-sheet.jpg`
- `human-approval-packet.json`

Local evidence bundle SHA-256: `8137f186e560bf733ae8891637e5e03c0a341b077cf6edfb07218d1dca7d4b7f`.

No asset was uploaded, registered, approved, or published.


## Per-file fail-closed disposition refresh — run 39022262843

- Reconciliation workflow: [39022262843](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022262843). Artifact: [eng-p22-glb-evidence-39022262843](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022262843/artifacts/12096857305).
- Every one of the 933 manifest rows now has an explicit disposition, queue, reason and provisionality marker in `manifest-audit.csv` / `manifest-audit.json`. This includes 927 physical GLBs and 6 duplicate/non-physical manifest references.
- Disposition totals: 262 `QUARANTINE_SOURCE_RIGHTS_OR_SAFETY_REVIEW`; 665 `HOLD_UNMAPPED_RIGHTS_AND_RENDERER_REVIEW`; 6 `NON_PHYSICAL_OR_DEDUPLICATED_REFERENCE`. All physical assets remain `NOT_APPROVED`; approved assets = 0. This completes the *initial fail-closed disposition assignment*, not the human/legal/visual/category review or publication approval.
- Integrity remains 927/927 valid containers, zero hash/size mismatch, zero missing/ambiguous files. Embedded texture byte fingerprinting resolved 1,639 payloads, with 1,234 unique hashes and zero unresolved payloads. Fingerprints do not prove rights or source attribution.

## ENG-P23 run 39020863350 failure and retry

- [Run 39020863350](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39020863350): acquired-avatar regression passed, but Android's emulator took approximately 526 seconds to report boot complete, then the emulator-runner action failed on `adb shell input keyevent 82` with exit code 224 / broken pipe. The React Native build/runtime test never started, and no Android evidence artifact was produced. This is a confirmed emulator-runner failure, not a confirmed asset/rendering defect.
- [Commit ed0f740](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/ed0f7402945b7026508e95ee80f6d59f2fa72d72) changes the Android CI image to API 34 / Pixel 2 and disables the failing animation-disable command; concurrency group was bumped so the prior run is not cancelled. Retry [39022292743](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022292743) must be inspected for runtime PASS marker, log and screenshot before acceptance.
- API smoke failure on the owner-release-decision conflict test was also confirmed. [Commit da3e521](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/da3e521a7a52cd00f9f1f8338f145736c4f888e7) moves immutable decision replay/conflict checks before current release gates. The fix remains unverified until its next CI run completes.

## Current gate decision

ENG-P22 remains `in_progress`: provisional dispositions are assigned, but per-file rights/likeness, texture source, category mapping, visual/moderation and renderer release gates are not cleared. ENG-P23 remains `in_progress`: actual Android and iOS runtime artifacts/screenshots with PASS markers are still required. ENG-P24 remains `not_started`; no asset was approved, registered, uploaded or published, and no Supabase mutation was performed.
