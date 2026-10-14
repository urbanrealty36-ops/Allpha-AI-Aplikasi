# ALLPHA FIXED PHASE PLAN
**Status:** Satu-satunya rencana operasional phase engineering  
**Product authority:** `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md`  
**Agent rules:** `AGENTS.md`  
**Branch:** `main` · **Monorepo:** `urbanrealty36-ops/Allpha-AI-Aplikasi`  
**Last reconciled:** 2026-10-14

> Dokumen ini adalah satu-satunya acuan operasional untuk urutan ENG phase, status, cakupan empat aplikasi, dependensi, aset 3D, dan pekerjaan berikutnya. Master PRD tetap menjadi sumber kebenaran produk. Jangan membuat phase baru, roadmap paralel, status board terpisah, atau dokumen phase rutin lainnya.

## 1. Aturan tetap
1. PRD product phase dan engineering phase adalah namespace berbeda. Pertahankan pemetaan yang eksplisit; jangan mengganti nomor untuk menyamarkan pekerjaan yang terlewat.
2. Engineering phase kanonis ENG-P00–ENG-P37. ENG-P37 hanya validasi lintas-domain dan release, bukan implementasi fitur yang belum ada.
3. Phase hanya dianggap selesai sesuai status PRD: `not_started`, `in_progress`, `blocked`, `implemented`, `integration_verified`, `acceptance_passed`, `production_verified`. Kode, dokumen, CI hijau, file di Storage, atau screenshot saja tidak membuktikan keseluruhan journey.
4. Setiap phase wajib memetakan keempat aplikasi di bawah sebagai `CHANGE`, `INTEGRATE`, atau `NOT AFFECTED` disertai alasan spesifik. Tidak boleh ada repo yang terlupakan atau kolom kosong.
5. Kerjakan langsung di `main` sesuai arahan pemilik. Implementasikan fitur, jalankan pemeriksaan otomatis yang relevan, perbaiki kegagalan, lalu lanjutkan. Hindari approval manual dan workflow administratif yang tidak perlu.
6. Satu sumber data dan business truth: `apps/api` + database kanonis Supabase `AllphaAiAplikasi-db` (`dvdziauyvuhcnqhrrvww`). Tidak membuat database kedua, registry domain duplikat, atau akses istimewa dari client.
7. Jangan klaim tes device, integrasi real, visual QA, migrasi, atau produksi jika belum benar-benar dijalankan.
8. Pertahankan Master PRD, `AGENTS.md`, dokumen arsitektur yang benar-benar dibutuhkan, dan panduan secrets/environment. Dokumen phase/status duplikat tidak dipertahankan. Dokumen yang berisi keputusan/kontrak teknis yang masih aktif hanya dipertahankan bila memang dirujuk dan tidak menggandakan phase plan.

## 2. Kontrak eksekusi empat aplikasi
Satu monorepo memiliki tepat tiga aplikasi client/frontend (`apps/web`, `apps/client` Android/iOS, `apps/super-admin`) dan satu backend kanonis (`apps/api`, Python/FastAPI). Jadi bukan empat frontend dan bukan empat repo terpisah; backend adalah jalur wajib untuk business logic dan data bisnis.

| Area aplikasi | Lokasi | Tanggung jawab | Bukti implementasi yang relevan |
|---|---|---|---|
| Web | `apps/web` | Next.js web app, responsive UI, web spatial renderer | source screen nyata, API terhubung, build/lint dan journey UI |
| Backend/API | `apps/api` | FastAPI, domain/service, authorization, API contracts, migrations, asset catalog/manifest dan lifecycle | pytest/API contract, migrasi jika perlu, permission/negative tests dan integrasi |
| Native Client | `apps/client` | aplikasi end-user Android dan iOS; bukan PWA | project native buildable, source screen/navigation, API client/session, Android build/test dan iOS build/test bila toolchain tersedia |
| Super Admin | `apps/super-admin` | console operator terpisah untuk pengelolaan domain dan operasi berizin | source UI nyata, API berotorisasi, build/test dan privileged-action tests |

Shared contracts boleh ditempatkan di `packages/contracts` jika benar-benar diperlukan; jangan membuat lapisan/package kosong hanya untuk memenuhi struktur. Web, Client, dan Super Admin menggunakan API resmi. Tidak ada business logic atau akses istimewa yang diduplikasi di client.

### Per-phase repo coverage (wajib, ringkas)
Sebelum coding, catat di commit/pekerjaan phase yang sedang dilakukan:
- **Web:** CHANGE / INTEGRATE / NOT AFFECTED + alasan.
- **API/DB:** CHANGE / INTEGRATE / NOT AFFECTED + alasan.
- **Native Client Android/iOS:** CHANGE / INTEGRATE / NOT AFFECTED + alasan.
- **Super Admin:** CHANGE / INTEGRATE / NOT AFFECTED + alasan.
- **Checks:** perintah otomatis relevan dan hasil sebenarnya.
Tidak perlu membuat file checklist/report terpisah untuk setiap phase. Update tabel phase ini saat status atau pekerjaan berikutnya berubah.

Aturan anti-kelalaian: satu phase tidak boleh dianggap selesai jika suatu aplikasi yang diperlukan oleh journey tidak mempunyai implementasi atau integrasi yang nyata. `README.md`, folder kosong, mock UI, dan placeholder bukan implementasi. Jika satu aplikasi memang belum tersentuh, phase tetap `in_progress` dan pekerjaan dilanjutkan di phase pemiliknya; jangan membuat phase baru hanya untuk menutupi kelalaian.

## 3. Fixed phase map dan status kerja saat rekonsiliasi

| Phase | Cakupan tetap | Status saat rekonsiliasi | Fokus/entry berikutnya |
|---|---|---|---|
| ENG-P00 | Product contract dan delivery governance minimum | in_progress | Pertahankan dokumen ini sebagai satu-satunya phase plan; jangan menambah status board terpisah |
| ENG-P01 | Platform foundation dan deployable thin slice untuk Web, API, Native Client, Super Admin | in_progress | Coverage: Web=INTEGRATE (Next.js + CORS/API origin); API=CHANGE (FastAPI readiness fail-closed, CORS allowlist, auth/error security regression tests); Native Client=CHANGE (Expo Android/iOS, SecureStore session + GET /v1/me, native export scan for privileged key patterns); Super Admin=CHANGE (live diagnostics, privileged operations tetap dibatasi). Stack native: ADR-0001; stack backend/engine Python + FastAPI: ADR-0002. CI retains Android APK artifact and iOS simulator build evidence; three npm lockfiles were generated by successful real installs and committed to main, and ENG-P01 CI now uses npm ci. Real Supabase auth/profile/logout smoke script and optional configured CI job are implemented. Integration update (2026-10-14): Railway target project `focused-tranquility` is verified by exact project ID `1e49a488-0f0a-4a25-9961-f1e6c19eebdd`. Independent services now exist for `apps/api` (`allpha-api.up.railway.app`), `apps/web` (`allpha-web-production.up.railway.app`) and `apps/super-admin` (`allpha-super-admin-production.up.railway.app`), all from this monorepo `main`; native app remains an Android/iOS build artifact, not a Railway HTTP service. Canonical API/Supabase public build configuration is now provided to CI. API domain target port is 8080, matching observed Uvicorn `$PORT`. Railway production service configuration was re-inspected and explicitly reconciled: API root `/apps/api` + `Dockerfile` + API-only watch patterns; Web root `/apps/web` + Web-only watch patterns; Super Admin root `/apps/super-admin` + Admin-only watch patterns. Native `apps/client` is not a Railway HTTP service. `docker-compose.yml` had invalid indentation in Web build args and omitted the separate Super Admin service; this was corrected. A dedicated Super Admin Dockerfile was added for local Compose, while its Next.js runtime remains compatible with the existing Railway Railpack `npm start` configuration. Compose now models API/Web/Admin separately. API Docker default/EXPOSE port is aligned to Railway `8080` while local Compose explicitly overrides to `8000`. ENG-P01 CI now validates Compose configuration and builds API/Web/Super Admin images. These are configuration/code changes; the newly triggered CI and Railway deployments must still pass before claiming deployment acceptance. Acceptance gaps remain: observe latest CI after this change, perform a lightweight authenticated Supabase/API smoke only when credentials are readily available, browser/native device smoke, verify all 3 Railway deployments after env-triggered builds, and review evidence. The optional real-Supabase and staging tenant-isolation jobs were removed from the default workflow to avoid secret-heavy CI setup; these live integration checks are deferred and are not represented as passed. Add mandatory source-to-engine mapping and direct database access audit for all three clients (`apps/web`, `apps/client`, `apps/super-admin`): allow Auth/session only as designed; trace every `.from(...)`, `.rpc(...)`, Storage/Realtime and provider SDK call; route business/domain operations through `apps/api` and canonical engines. Verify `AGENTS.md` section 12 before implementation. Do not claim full production integration or audit completion until these pass. Security follow-up (2026-10-14): expanded client/provider inventory and endpoint→data/RLS/grant map are recorded in `docs/SECURITY/ENG-P01_CLIENT_API_ACCESS_AUDIT.md`. Corrected the confirmed `profiles.account_status` grant mismatch by routing deactivation through a new `auth.uid()`-scoped RPC and adding handler regression; added invalid/expired token and manipulated cross-tenant ID handler regressions. Added migration `20261014100000_eng_p01_scoped_account_deactivation_rpc.sql`, not applied to canonical production. Full ENG-P01 CI on the current `main` phase-plan commit `381a3089c0c4e6f147a005cbfc0ce73cb062c036` completed successfully: run [`38476060170`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38476060170) passed the API regression tests, Web typecheck/build/container, Super Admin typecheck/tests/build/container, native iOS simulator build, native Android SDK installation and build job, and Compose validation. The Android SDK installation failure from run `38469272438` is no longer reproduced in this run. The lightweight Allpha Smoke run [`38476060223`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38476060223) also passed, but covers only API tests and Web build/typecheck. The optional real Supabase auth journey and staging tenant-isolation jobs have been removed from the default workflow to keep CI lightweight. Real authentication and cross-tenant isolation remain `DEFERRED / NOT VERIFIED`; no workflow success is treated as evidence for those live checks. Latest verification update (2026-10-14): run [`38490988430`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38490988430) on commit `c6ae8ae32c53c825c6a27e35bf3d84c2f832eb21` passed Allpha Smoke (API tests and Web build). A prior Smoke run on `3800125cf84fdbc696fd5fe80c55c9dfc569824a` failed because the readiness test expected `configured` while `/readyz` correctly returns `reachable` after successful live-probe simulation; assertions were corrected in `c6ae8ae`. ENG-P01 run [`38490988221`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38490988221) for `c6ae8ae` is pending; an older run is still processing Android/iOS builds after its API test failure and must not be counted as acceptance. Latest focused fix (2026-10-14): Super Admin `/readyz` UI previously treated dependency state `reachable` as misconfigured because it expected `configured`; it now checks only the required `database` and `authentication` dependencies for `reachable`, consistent with FastAPI's readiness contract. Added a source smoke assertion for this mapping. Commits: `5149e502ed2042999a56760d8e5a3bee62e5e481` and `0aa716ae48bb117d5355cc1db32bc91e818b051a`. Latest verification update (2026-10-14): ENG-P01 run [38493682448](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38493682448) on `b3e7fba1c233819e0dc143ae4e0cc19188d4431e` completed `success` across Android debug APK, iOS Simulator package, API regressions, Web, and Super Admin; Allpha Smoke [38493682475](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38493682475) also passed. Both native artifacts were downloaded and checksum-verified: Android artifact archive SHA-256 `c4467442195ca5399aa60d67388df700c275cd8c2a17547aa09eb7d234404af4`, APK SHA-256 `e82ddcce49c5f3fa7109f85e803d615a19564cccbc0418f0b96888bd84bffe34`; iOS artifact archive SHA-256 `321cb47fbb6d4e9ed04070113f3b31c1cbee8618e70d3943fdf06b518ec5cb01`, nested simulator app ZIP SHA-256 `ae61a19e3795b10e76b69de2d6a7d6acb6fbaccab202199ee9774dfe8bad8c39`. Each inner-file checksum matches its artifact's included `SHA256SUMS`. CI and artifact evidence is complete for this run, but ENG-P01 remains `in_progress` until authenticated end-to-end/device acceptance, external deployment checks, and live two-tenant integration in isolated non-production are verified. Supabase connector still exposes only canonical production and no development branches; do not test tenant isolation against production. Runtime URL probes from this execution environment failed DNS resolution; deployed Web/Admin/API responses are not independently verified here. Live two-user isolation and migration verification remain deferred; do not run destructive checks against canonical production. Read-only Supabase inspection confirms `request_account_deactivation` is absent from production schema; migration `20261014100000_eng_p01_scoped_account_deactivation_rpc.sql` is present in repo but not applied. Supabase connector currently lists no development branches and exposes only the canonical production project, so non-production integration remains blocked; do not create a new project/branch or run real tenant tests against production. Keep ENG-P01 `in_progress`.
| ENG-P02 | Database, authentication, authorization, tenant isolation | in_progress | Evidence update (2026-10-14): source commit [`4b41a5d`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/4b41a5d8f7448297c3a61640d629f57b5da0d318) explicitly introduced `20261013052302_eng_p02_identity_authorization_baseline.sql` as a **reconstructed** baseline for fresh databases; its own header says the version was already recorded as applied. Supabase migration history records ENG-P02 versions `20261013052302`, `20261013052409`, `20261013052557`, `20261013052733`, `20261013052744`, and `20261013090730`, but history provides version/name—not a checksum or proof of the SQL originally executed. Read-only live catalog inspection (2026-10-14) found none of `organizations`, `organization_memberships`, or `audit_events` in any schema; `public` currently contains only seven application tables and all seven have RLS enabled. Therefore current source SQL is confirmed reconstructed, while exact byte-for-byte divergence from the historical applied SQL cannot be proven from available migration metadata; live schema is inconsistent with the current reconstructed files and recorded version labels. No DDL was run against production. Supabase connector reports only canonical production project `dvdziauyvuhcnqhrrvww` and zero development branches; per constraint, no project/branch was created. Real two-identity owner/member and cross-tenant RLS tests, fresh-install/upgrade migration tests, and service/repository refactor remain BLOCKED / NOT VERIFIED until an already-existing isolated non-production environment is made available. CI run [`38496984369`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38496984369) passed API regression, Android, iOS simulator, Web, and Super Admin jobs, but these tests do not exercise live organization tables/RLS. Next: recover/compare the historical SQL or authoritative schema snapshot; design a versioned forward-repair migration only after schema contract and ownership are reconciled; run fresh-install + upgrade + grants/policies/functions/trigger checks and real two-user isolation in isolated non-production; only then refactor Organizations/Memberships handler → service → repository and consider a status transition. API=CHANGE (existing mocked handler regressions remain useful but are not integration evidence); Web=NOT AFFECTED; Native Client=NOT AFFECTED; Super Admin=NOT AFFECTED for this bounded database/auth slice. Keep ENG-P02 `in_progress`; do not apply a repair to production or claim `integration_verified`/`acceptance_passed`.
| ENG-P03 | Human identity, profile, settings, privacy | in_progress | Evidence update (2026-10-14): Web=INTEGRATE (existing authenticated identity screen/API contracts retained); API/DB=CHANGE/INTEGRATE (added authenticated `POST /v1/me/consents`, schema restricts consent type/version/granted and derives `user_id` from authenticated identity; appended API regressions for forged identity fields, self-scoped consent insert and unauthenticated consent recording); Native Client=CHANGE (profile edit, avatar URL, bio, username, locale, visibility, theme, notification preferences, discoverability and deactivation-request controls added using FastAPI); Super Admin=NOT AFFECTED (no operator-facing identity workflow in this slice). CI at commit `63fd0fff` passed full ENG-P01 checks including Android debug APK, iOS simulator build, Web, Super Admin, API tests, and Compose; the real Supabase auth journey step and tenant-isolation job reported `success` but only their wrapper steps ran and do NOT prove a configured live integration. Latest consent API regression workflow is running. No production migration or DB mutation was executed. Blockers before acceptance: confirm latest CI; test authenticated save/settings/consent journey against dedicated non-production Supabase (none currently available); add consent capture UI only after canonical terms/privacy policy versions are defined; validate deactivation RPC migration/application safely outside production; verify native user journey/device evidence. Keep phase `in_progress`. |
| ENG-P04 | Social Graph: follow/relationship, block/mute, interest graph dan privacy | in_progress | Status update 2026-10-14: API/DB=CHANGE/INTEGRATE (canonical production already contains `social_edges` and `user_interests`, RLS enabled, Realtime publication registered; authenticated endpoints cover graph, edge mutations, follow-request accept/reject, and interests; API now returns `incoming_requests` scoped to authenticated recipient). Web=CHANGE (Social Graph tab supports follow/block/mute, incoming request accept/reject, relationship removal and interest CRUD via FastAPI); Native Client=CHANGE (same authenticated API-backed journey in Expo app); Super Admin=NOT AFFECTED (no operator surface required). CI reported GREEN by project owner; still verify the runs associated with these latest API/Web/Native commits. Important source-of-truth gap: applied production migration differs from repo source due to restricted column UPDATE grant (`status` only), and Realtime publication migration must be committed to repo. Remaining acceptance: reconcile migration files/history without reapplying production DDL, run API/Web/Admin/Android CI on latest commits, inspect rendered Web and Android journeys, validate API error/loading/empty states, and capture non-production authenticated acceptance when available. No fake production users/data. Keep ENG-P04 `in_progress` until all evidence is recorded. Do not close ENG-P03 or ENG-P01/02 dependencies.
| ENG-P05 | AI Agent identity, ownership, persona, passport | in_progress (implementasi historis sudah ada di bawah label ENG-P04) | Pertahankan kode/migrasi yang sudah ada, referensikan secara kanonis sebagai ENG-P05, tutup integrasi yang benar-benar kurang tanpa mengulang implementasi |
| ENG-P06 | Agent Studio, skills, tools, capability governance | not_started | Setelah identity/ownership siap |
| ENG-P07 | Knowledge ingestion, document processing, Agent learning | not_started | Upload, proses, status job, provenance, delete/retry |
| ENG-P08 | Agent memory, retrieval, context assembly, privacy isolation | not_started | Memory lifecycle dan owner/tenant isolation |
| ENG-P09 | AI Gateway, Model Router, provider adapters, cost policy | not_started | Provider-neutral routing, metering, quota dan budget |
| ENG-P10 | Agent Runtime, tool execution, conversation sessions | not_started | Runtime terikat permission, budget, tool contracts |
| ENG-P11 | Durable workflow orchestration, checkpoint/resume | not_started | Durable state, retry/idempotency, cancellation/resume |
| ENG-P12 | Skill Challenge, evaluation, achievements/rewards | not_started | Evaluasi traceable, anti-abuse dan reward ledger |
| ENG-P13 | Content creation dan media pipeline | not_started | Satu content model, upload, preview/publish/error recovery |
| ENG-P14 | Social feed, ranking, interactions dan controls | not_started | API + seluruh client yang terdampak |
| ENG-P15 | Reels, short video/audio, media consumption | not_started | Playback, adaptive behavior dan moderation |
| ENG-P16 | Stories, moments, temporary content | not_started | Expiry ditegakkan server-side |
| ENG-P17 | Search, discovery, trends, recommendations | not_started | Search API/index dan privacy-aware UI |
| ENG-P18 | Messaging Human/Agent, delivery/realtime | not_started | Membership authorization, delivery states dan reconnect |
| ENG-P19 | Communities, collaboration, missions/workspaces | not_started | Membership, access grants, moderation |
| ENG-P20 | Notification center dan delivery orchestration | not_started | Preferences, dedupe, retry; push native ketika dikonfigurasi |
| ENG-P21 | Spatial domain, Universe hierarchy, navigation | not_started | Universe/Galaxy → World → District → Zone → Booth/POI → scene object; ID/coordinate/landmark contract bersama Web dan native |
| ENG-P22 | Theme Builder, GLB Asset Pipeline, catalog/manifest | not_started | Inventaris file nyata, provenance/license, hash/size, parse/format, kategori 14 template, versi, API catalog dan alur developer preview-to-renderer |
| ENG-P23 | World Renderer, City Districts, buildings, landmarks, booths, spatial interactions | not_started | Gabungkan scene memakai canonical Scene Schema dan entity IDs; render GLB yang dipetakan dari manifest di Web dan native; validasi loading, fallback, navigasi dan performa |
| ENG-P24 | Human avatar, AI Character, uniforms, animation contract | not_started | Rig/animation capabilities diverifikasi dari asset; tidak mengklaim animasi yang tidak didukung |
| ENG-P25 | Live Experience dan virtual stage | not_started | Template stage, role, create/join/manage journey lintas aplikasi |
| ENG-P26 | Realtime streaming, voice, camera dan live animation | not_started | Permission kamera/mic, reconnect, native/web transport dan fallback |
| ENG-P27 | Events, scheduling, attendance | not_started | Timezone, capacity, join/cancel dan notifikasi |
| ENG-P28 | Agent catalog/marketplace/service discovery | not_started | Listing, permission, compatibility, moderation |
| ENG-P29 | Commerce, Booth Tenant, creator economy/revenue share | not_started | Order/ledger/settlement dan operator workflows |
| ENG-P30 | Freemium, subscription, credits, billing/payment settlement | not_started | Server-verified payment, idempotent webhook, ledger dan reconciliation |
| ENG-P31 | Ads, sponsorship, spatial ad inventory | not_started | Consent, labeled placements, spend/impression metrics |
| ENG-P32 | Trust, safety, moderation, reputation, anti-fraud | not_started | Enforcement lintas seluruh aplikasi/domain |
| ENG-P33 | Analytics, insights, product intelligence | not_started | Role-scoped, privacy-preserving metrics |
| ENG-P34 | Super Admin Control Plane, governance, operations | not_started | Implementasi nyata di `apps/super-admin` dengan API privileged yang terotorisasi |
| ENG-P35 | Developer Platform, public API, Agent interoperability | not_started | Credentials, scopes, quotas, webhook dan contract docs |
| ENG-P36 | Observability, reliability, AI evaluation, cost operations | not_started | Metrics/log/alerts/evaluation dan runbook operasional |
| ENG-P37 | Final cross-domain E2E, security regression, release gate | not_started | Validasi journey end-to-end setelah fitur tersedia; tidak boleh menutupi fitur yang belum diimplementasikan |

**Makna status:** status di atas adalah baseline konservatif dari bukti repo yang telah diperiksa, bukan klaim audit penuh semua domain. Perbarui hanya saat ada bukti nyata. Status historis Agent Identity berlabel ENG-P04 tidak mengubah definisi ENG-P04=Social Graph dan ENG-P05=Agent Identity.

## 4. Urutan kerja langsung berikutnya
1. **ENG-P01 — foundation:** React Native + Expo native Android/iOS (ADR-0001), API-backed session/profile slice, Super Admin console terpisah, dan CI API/Web/Super Admin/native. Pertahankan status `in_progress` sampai bukti acceptance journey dan kedua platform tersedia; jangan membuat phase baru.
2. **ENG-P02/P03 — integrasi native:** sambungkan login/session, profile, preferences dan privacy ke API/Supabase yang sudah ada; hindari duplikasi Web.
3. **ENG-P04 — Social Graph:** bangun API/data/policy dan screen pada setiap client yang terdampak.
4. **ENG-P05 — Agent Identity:** lanjutkan kode yang sudah ada dan lengkapi integrasi; jangan ulang dari nol.
5. **ENG-P21/P22/P23 — spatial/GLB:** setelah foundation API dan native renderer dapat dipakai, lakukan asset inventory dan manifest mapping, lalu renderer integration dan district assembly sesuai ketentuan bagian 5.
6. Lanjutkan phase lain menurut dependensi Master PRD. Satu feature dikerjakan sebagai vertical slice lintas aplikasi yang terdampak.

## 5. Kontrak implementasi 3D GLB, District/Landmarks, dan 14 Theme Categories

Bagian ini merupakan spesifikasi kerja untuk ENG-P21, ENG-P22, ENG-P23, dan ENG-P24. **Keberadaan script/workflow akuisisi atau GLB di Storage bukan bukti bahwa katalog lengkap, file telah dipetakan benar, District telah dirakit, atau aset telah tampil di UI.**

### 5.1 Pipeline kanonis
1. **Inventory nyata:** catat setiap file/asset dengan stable asset ID, nama, sumber URL/repo, provenance, license evidence/source terms, object path, ukuran bytes, SHA-256, file format, versi dan status. Jangan mengarang inventory berdasarkan jumlah target.
2. **Acquire/import:** developer memasukkan asset melalui alur yang ditentukan; pertahankan original bytes dan sumbernya. Jangan unduh ulang seluruh koleksi jika aset tersedia.
3. **Basic structural check otomatis:** validasi GLB header/chunks/JSON, checksum/size, external URI dependencies, scene/mesh/material/texture/animation metadata, dan error yang bisa ditindaklanjuti. File gagal ditandai jelas; jangan diam-diam dianggap valid.
4. **Category mapping:** klasifikasikan berdasarkan metadata, geometri dan konteks yang benar-benar diamati. Nama file/heuristik hanya kandidat. Jangan default semua aset tak dikenal menjadi District atau memaksa satu asset ke kategori yang tidak didukung.
5. **Catalog + immutable manifest:** backend adalah pemilik canonical asset registry. Manifest memuat asset ID/version, category, checksum, size, storage reference, compatibility/capabilities, status dan metadata penempatan yang diperlukan. Hindari private Storage URL yang di-hardcode ke UI.
6. **Developer preview:** aset yang tersedia untuk developer dapat dipreview secara sederhana setelah pemeriksaan format dasar; tidak perlu approval manual berlapis untuk preview lokal. Preview tidak berarti hak publik, entitlement, moderation clearance atau production publication.
7. **Publish/use:** gunakan lifecycle/catalog API kanonis untuk aset yang boleh ditayangkan ke audience yang sesuai. Jangan menulis langsung ke registry/database dari client atau membuat registry kedua. Status publik dan hak/lisensi tetap harus jelas.
8. **Renderer integration:** Web dan Native Client membaca scene + manifest dari API dan memuat GLB dengan loading/error/retry, cancellation, cleanup, low-detail fallback, dan batas performa yang sesuai perangkat.
9. **District assembly:** scene disusun dari canonical World/District/Zone/Booth/POI IDs dan scene schema deklaratif. GLB hanya visual asset; tidak menentukan permission, owner, commerce, billing, atau status bisnis.
10. **Evidence:** per asset/scene simpan hasil pemeriksaan yang relevan dan link commit/build/test. Tidak perlu dokumen per asset jika metadata dan hasil otomatis sudah berada di manifest/report.

### 5.2 Empat belas category keys kanonis
Kunci di bawah tidak boleh diubah diam-diam karena dipakai sebagai kontrak kategori.

| Key | Makna penggunaan | Contoh objek/placement yang cocok (bukan klaim asset tersedia) |
|---|---|---|
| `universe` | ruang/komposisi Universe utama | scene/visual Universe |
| `galaxy` | Galaxy dan komposisi bintang | galaksi, nebula, starfield |
| `world` | environment World | terrain, landscape, environment |
| `orbit` | orbit dan objek orbit | orbit ring, satellite/orbit visual |
| `capsule` | Content Capsule/portal container visual | capsule/pod/container |
| `district` | elemen kota dan District | city blocks, streets, buildings |
| `booth` | booth/tenant/retail POI | kios, store, booth, tenant space |
| `content-feed` | surface konten/media | screen, billboard, content display |
| `agent-character` | karakter visual Agent | character/avatar/robot dengan rights/rig metadata |
| `live-stage` | panggung dan studio Live | stage, podcast, presentation, classroom |
| `human-live` | elemen human camera/live participant | live-person setup/visual elements; bukan pengganti izin kamera |
| `sticker-social` | sticker/reaction sosial | sticker, emoji, reaction object |
| `animation` | asset/clip/rig animasi | rig, animation clip, motion asset |
| `navigation-fx` | navigasi dan efek visual | portal, gate, waypoint, navigation FX |

Target desain **25 Theme × 14 kategori = 350 slot template**. Ini matriks kebutuhan, bukan klaim 350 file unik atau aset yang sudah disetujui. Setiap slot harus mencatat template/theme ID, category key, asset ID/version yang ditautkan bila tersedia, status dan fallback. Slot boleh berstatus missing/unmapped; jangan membuat aset fiktif untuk memenuhi angka.

### 5.3 District kota dan landmarks
- District harus berupa scene yang tersusun dari beberapa aset/objek, bukan satu GLB besar tanpa entity mapping.
- Setiap landmark/POI punya stable domain ID, parent District/Zone ID, transform/coordinate, scale convention, interaction type, access/visibility, theme reference dan optional asset ID/version.
- City GLBs dipakai sebagai building/block/road/landmark presentation layer. Simpan identitas jalan, gedung, landmark, portal, booth dan POI dalam scene/domain data agar dapat diperbarui tanpa mengubah business IDs.
- Pemetaan landmark wajib berasal dari inventory dan bukti nyata (nama/metadata/geometri/visual preview). Jangan mengklaim landmark kota tertentu tersedia hanya berdasarkan nama file.
- Integrasi ke UI/UX berarti scene benar-benar dipanggil oleh route/screen, data berasal dari API/manifest, dan pengguna melihat loading/success/error/fallback yang berfungsi. Menambahkan file GLB ke Storage atau menampilkan thumbnail tidak memenuhi syarat.
- Uji desktop dan Android native; uji iOS bila toolchain/device tersedia. Catat platform yang belum dapat diuji tanpa menghambat implementasi lain yang bisa dikerjakan.

### 5.4 Status asset/scene yang jujur
- `not_started`: belum ada implementasi nyata.
- `in_progress`: sebagian kode/asset tersedia; journey belum lengkap.
- `implemented`: alur kode dasar tersedia dan checks relevan lulus.
- `integration_verified`: API, catalog/manifest, storage dan renderer diuji bersama pada environment yang disebutkan.
- `acceptance_passed`: scene/asset journey diterima dengan bukti tampilan dan interaksi yang relevan.
- `production_verified`: hasil diuji di deployment produksi yang nyata.
Jangan gunakan kata “published” hanya karena file berhasil diupload. Bedakan developer preview dari publikasi audience-facing.

### 5.5 Kondisi repo saat ini yang telah teramati
- `tools/3d-assets/acquire_glb_assets.py` adalah alat akuisisi/audit katalog sumber GLB dan memberi kategori awal berbasis heuristik. Kategorisasi heuristik bukan bukti visual/semantic QA.
- `tools/3d-assets/audit_glb_readiness.py` melakukan pemeriksaan struktur, ukuran, hash dan flags; outputnya sendiri menegaskan bahwa ini bukan legal clearance, visual QA, malware scan, GPU performance atau renderer compatibility.
- Workflow `.github/workflows/allpha-glb-asset-acquisition.yml` mengunduh aset ke artifact workflow; itu sendiri bukan publikasi ke katalog produksi.
- Workflow `.github/workflows/allpha-glb-asset-readiness.yml` mengaudit artifact yang ada; itu sendiri bukan integrasi renderer.
- Tree repo yang diperiksa pada rekonsiliasi ini belum menunjukkan implementasi 3D renderer, katalog scene, atau data inventory 350 slot di monorepo ini. Karena itu ENG-P21/P22/P23 tetap belum diverifikasi dan perlu implementasi/integrasi nyata; jangan menganggap aset dari repository/proyek lain otomatis berada di repo atau Storage kanonis ini.

## 6. Cara eksekusi setiap phase
1. Baca Master PRD, `AGENTS.md`, bagian relevan dari file ini, lalu code/migration/tests yang benar-benar terkait.
2. Periksa empat area aplikasi dan tandai CHANGE / INTEGRATE / NOT AFFECTED beserta alasan.
3. Implementasikan vertical slice end-to-end pada aplikasi yang terdampak; tambahkan migration hanya bila perlu.
4. Jalankan pemeriksaan otomatis relevan, perbaiki kegagalan, dan jangan mengarang hasil device/production.
5. Commit langsung ke `main`.
6. Perbarui status di tabel dokumen ini hanya jika status/next action berubah. Laporan di percakapan cukup menyebut commit, repo yang berubah, checks yang dijalankan, gap nyata dan phase berikutnya.

Tidak boleh membuat phase-plan per phase, status CSV, crosswalk baru, evidence registry duplikat atau report file rutin untuk menggantikan update ini.

## 7. Invariants arsitektur
- Master PRD v3.0.0 menentukan kebutuhan produk; dokumen ini menentukan urutan eksekusi engineering.
- Target surface: native Android/iOS, Web, Super Admin terpisah, Developer Console. PWA bukan target.
- Database kanonis: Supabase `AllphaAiAplikasi-db` (`dvdziauyvuhcnqhrrvww`).
- Domain/business truth, asset catalog dan lifecycle tetap di backend/API resmi.
- Tidak ada secrets di client, fake data produksi, atau akses Storage privat yang di-hardcode.
- Scene/world data bersifat deklaratif dan tervalidasi; GLB tidak memberi hak/permission bisnis.
- Untuk fitur yang melibatkan user, lakukan check minimal untuk owner/authorization/privacy dan failure/retry. Jangan menunda semua hardening ke ENG-P37.
- Pilih automated checks proporsional; jangan menambah gate manual atau CI berat yang tidak memperbaiki correctness.

## 8. Definition of done per phase
Sebelum memajukan status:
- [ ] Scope dan acceptance journey sesuai Master PRD.
- [ ] Keempat app surfaces dipetakan; setiap area memiliki alasan eksplisit bila tidak terdampak.
- [ ] Source code nyata tersedia pada setiap area yang diwajibkan (native project tidak boleh hanya README).
- [ ] API/data dan UI menggunakan sumber data nyata, bukan mock yang disamarkan.
- [ ] Automated checks relevan lulus atau keterbatasan yang nyata disebutkan.
- [ ] Integrasi/device/production hanya ditandai jika benar-benar diperiksa.
- [ ] Status, commit, gap dan next action diperbarui di dokumen ini.

## 9. Berikutnya
**Pekerjaan berikutnya adalah ENG-P01: implementasi fondasi native Android/iOS di `apps/client`, lalu menghubungkan ENG-P02/P03 ke native journey yang nyata.** Jangan membuat phase Android/iOS baru. Pekerjaan 3D dilanjutkan pada ENG-P21–ENG-P24 dengan kontrak di bagian 5, bukan lewat roadmap atau dokumen terpisah.
