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
- API smoke failure on the owner-release-decision conflict test was confirmed and fixed in [commit da3e521](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/da3e521a7a52cd00f9f1f8338f145736c4f888e7). [Allpha Smoke run 39022366546](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022366546) subsequently passed: 463 API tests passed (1 warning), with Web build and Native client checks passing.

## Current gate decision

ENG-P22 remains `in_progress`: provisional dispositions are assigned, but per-file rights/likeness, texture source, category mapping, visual/moderation and renderer release gates are not cleared. ENG-P23 remains `in_progress`: actual Android and iOS runtime artifacts/screenshots with PASS markers are still required. ENG-P24 remains `not_started`; no asset was approved, registered, uploaded or published, and no Supabase mutation was performed.

## Confirmed native harness correction — runs 39018265467 / 39022553114

- Failed iOS run [39018265467](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39018265467) built and opened the Expo development client, but it waited for Metro at port 8081 while the command explicitly disabled the bundler. No `SPATIAL_DEVICE_TEST_RESULT:PASS` marker was emitted, and no screenshot was captured. This is a confirmed CI harness configuration defect.
- [Commit 4d394b8](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/4d394b85b54d1b1d66c5a514c2b569e1f8153a87) removes `--no-bundler` from Android/iOS test launches and validates runtime PASS marker plus PNG signature, dimensions and minimum size. [Commit ddd35ca](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/ddd35cae754ff9ef2a2430fed4c30d3c66adbd7c) fixes the PNG signature literal and preserves the active run by changing the concurrency group.
- [Run 39022553114](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022553114) is the latest revision with screenshot verification. It was still in progress at report time; no Android/iOS acceptance is claimed until both device logs and validated screenshots are retained.
- [Spatial renderer CI run 39022366475](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022366475) passed API contract, Native renderer and Web renderer jobs. This does not substitute for device evidence.


## Android run 39022553114 — confirmed harness failure and correction

- [Run 39022553114](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022553114) booted Android after a long wait but failed before building/running the test app: Expo reported that the expected repository-root `package.json` did not exist. The workflow resolved Expo/project root incorrectly. No Android PASS marker or screenshot was captured. Avatar regression itself passed and artifact [12097032660](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39022553114/artifacts/12097032660) was produced.
- [Commit 04288a5](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/04288a507e3c57179ab73e458ae482b2f35d72fc) uses the local Expo CLI under `apps/client/node_modules/.bin` with explicit `--project-dir apps/client` for both Android and iOS, and bumps concurrency to v6. Retry [39023821148](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39023821148) was in progress at report time. Acceptance remains blocked until both platform logs contain the PASS marker and the PNG validation step passes.


## Per-file source provenance normalization

Inspection of the downloaded source manifest found that canonical download links are stored under `url`, while the evidence report's `source_url` was blank. [Commit d7d407a](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/d7d407a011c8e32fc329a72cb405d767cc1947dc) now normalizes `source_url`, repository, source path, claimed license, source review state, and per-file rights/category/texture/visual/renderer review status. Reconciliation [39023923471](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39023923471) is running. This is an evidence-report correction only; no legal review is inferred and all assets remain unapproved.


## ENG-P22 source URL normalization verified — run 39023923471

- Run [39023923471](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39023923471) succeeded; artifact [12097593609](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39023923471/artifacts/12097593609). The audit CSV now includes canonical source URL, repository, path and license claim on all 933 manifest rows (0 blank source URLs). The 927 physical GLBs remain 927/927 valid with zero integrity mismatches; embedded image payload fingerprints: 1,639, unresolved 0.
- The report still records 668 `UNMAPPED_REQUIRES_REVIEW`, 265 `HEURISTIC_CANDIDATE_REQUIRES_REVIEW`, 262 `QUARANTINE_REQUIRED`, 671 `PER_FILE_RIGHTS_REVIEW_REQUIRED` (includes the 6 non-physical rows), 665 physical hold rows and 0 approved assets. The fields expose per-file review requirements, but do not certify legal rights, texture provenance, category suitability, or visual approval.


## Latest follow-up — native Expo CLI error corrected; per-file license evidence pointers (2026-10-17)

- [Run 39023821148](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39023821148) finished with Android and iOS failures at native prebuild. Both actual logs report `unknown or unexpected option: --project-dir`; Android emulator did boot, so the previous package-root blocker is resolved, but native execution did not start. No `SPATIAL_DEVICE_TEST_RESULT:PASS` markers or valid Android/iOS screenshots were retained. This is a confirmed Expo CLI invocation defect.
- [Commit 93c13d3](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/93c13d33e2022215ede1bbea04cd5a90fc97d750) removes the unsupported option and executes the repository-local Expo binary from `apps/client`. New run [39024893640](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39024893640) is running Android, iOS and actual-avatar regression; no device acceptance is claimed until it finishes and both markers/screenshots are validated.
- Expanded the per-row audit in [commit 9415bf9](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/9415bf95fee6f780c90b7e744ed93ae8ba2a46e5) with `source_license_evidence_url`, `source_texture_rights_evidence_url`, `license_scope_assessment`, and `distribution_derivative_rights_status`. These link each source group to its repository license/README evidence while explicitly distinguishing repository-level claims from asset-specific legal clearance. Reconciliation [run 39025011242](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39025011242) is producing the refreshed matrix.
- Source-level evidence findings: rostock/3DModels has a repository LICENSE and CC0 claim, but per-file content and third-party rights remain unverified; c-frame/valid-avatars-glb has a repository MIT license, which does not resolve likeness, attribution or derivative scope for the 232 physical avatar files; ramjigeddam/3d has no license-like root file and its physical models remain quarantined; SpectraStudios/SourceCityToolkit_glb has LICENSE/README files but the README's texture exceptions mean 219 embedded images still need source/rights mapping. A URL to a license is evidence to inspect, not proof that every embedded component is covered.
- All 927 physical GLBs remain `NOT_APPROVED`. The 668 category-unmapped rows and 265 heuristic candidates still require canonical human mapping; texture provenance and human visual/moderation review remain pending; renderer/device acceptance remains pending. No asset was registered, uploaded, approved or published, and no Supabase write occurred.

**Gate decision:** ENG-P22 `in_progress`; ENG-P23 `in_progress`; ENG-P24 `not_started`.


## ENG-P22 evidence matrix artifact verified — run 39025011242

- [ENG-P22 run 39025011242](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39025011242) succeeded; artifact [12098018030](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39025011242/artifacts/12098018030) inspected from the downloaded ZIP. The CSV contains 933 rows / 63 columns. All rows have non-empty `source_license_evidence_url` and `source_texture_rights_evidence_url`, with explicit license-scope and distribution/derivative-rights assessments.
- Source evidence was checked at repository-root level: rostock/3DModels contains LICENSE/README; c-frame/valid-avatars-glb contains LICENSE/README/avatars.json; ramjigeddam/3d root listing contains no license-like file; SpectraStudios/SourceCityToolkit_glb contains LICENSE/README. This establishes the location of source evidence only, not that each model and embedded image is legally redistributable or derivative-permitted.
- Audit counts: 927 physical GLBs valid, 0 integrity mismatch, 232 valid Meshopt fallback patterns, 1,639 embedded image hashes / 1,234 unique / 0 unresolved, 241 assets with skins, 8 with animation clips. Disposition remains 262 quarantine + 665 hold + 6 duplicate/nonphysical references. All 933 rows are `NOT_APPROVED`; approved assets = 0.
- Remaining per-file acceptance gaps: license and derivative rights need asset-specific review; c-frame likeness/attribution unresolved; 219 city textures need per-image source/rights mapping; all 933 visual reviews are pending; 668 categories unmapped and 265 heuristic-only; renderer/device acceptance is pending. No candidate was promoted based on a repository license URL.
- ENG-P23 retry [39024893640](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39024893640) remained in progress at this checkpoint. The previous run's `--project-dir` failure is corrected by commit [93c13d3](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/93c13d33e2022215ede1bbea04cd5a90fc97d750); acceptance still requires the actual final Android/iOS logs, PASS markers, and validated screenshots.

**Decision unchanged:** ENG-P22 `in_progress`; ENG-P23 `in_progress`; ENG-P24 `not_started`. No Supabase writes or asset lifecycle mutations were made.


## Run 39024893640 artifact and source-specific rights review

- The acquired-avatar regression job in [run 39024893640](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39024893640) is complete and passed. Artifact [12098546300](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39024893640/artifacts/12098546300) was inspected: GLTFLoader 232/232 pass (0 failures, 1,691 mesh nodes); browser texture decode + WebGL frame 232/232 pass, 564 texture images decoded, 1,698 draw calls, 13 sampled screenshots; Web and Native Meshopt decoders each 232/232 pass with 1,160 decoded buffer views. These checks do not substitute for Android/iOS renderer evidence.
- At the latest check, the overall run remains in progress. Android job 117373835910 and iOS job 117373836061 are still executing the actual React Native renderer step; no device artifacts have been uploaded, so there is no accepted device PASS marker or screenshot yet. No unproven code fix was made while those steps remained active.
- Source review found the c-frame conversion README links to upstream [VALID Avatar Library](https://github.com/xrtlab/Validated-Avatar-Library-for-Inclusion-and-Diversity---VALID), which also has an MIT LICENSE. The upstream README describes the library as 210 fully rigged avatars created for research/diversity and inclusion. The license links are useful provenance, but per-asset distribution/derivative rights and likeness/publicity review remain unresolved.
- [Spectra SourceCityToolkit README](https://github.com/SpectraStudios/SourceCityToolkit_glb/blob/main/README.md) explicitly warns that one or more textures use photographs from Textures.com and may not be redistributed by default. The 13 city GLBs remain on hold until affected embedded textures are identified per file and rights are documented. The Rostock catalog also links individual model URLs and declares CC0 at catalog level, but that is not conclusive proof for every third-party component.
- [Commit 935a4eb](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/935a4ebe080ffb31085f1611323105232b65442e) adds upstream source/license evidence fields for the avatar conversion. Reconciliation run [39026460210](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39026460210) is queued for the refreshed matrix.

**Decision unchanged:** all assets remain `NOT_APPROVED`; ENG-P22 and ENG-P23 remain `in_progress`; ENG-P24 remains `not_started`. No Supabase writes, registrations, approvals, or publications were performed.


## Upstream evidence matrix verified — run 39026460210

- [Run 39026460210](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39026460210) succeeded. Artifact [12098941661](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39026460210/artifacts/12098941661) was inspected: 933 manifest rows, 66 columns; repository license and texture evidence URLs are populated for all rows; upstream VALID source/license evidence URLs are populated for 234 c-frame manifest rows, and 699 other rows explicitly record that no upstream source link is recorded.
- Technical counts and fail-closed dispositions remain unchanged: 927 valid physical GLBs, 0 integrity mismatches, 1,639 embedded image hashes / 1,234 unique / 0 unresolved; 241 skinned assets; 8 assets with animation clips; 262 quarantine, 665 hold, 6 nonphysical/deduplicated references; 0 approved assets.
- [Run 39024893640](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39024893640) remains `in_progress` at latest poll. The acquired-avatar regression is complete and passed; Android and iOS device jobs remain active with no final artifacts. Device acceptance is pending.
