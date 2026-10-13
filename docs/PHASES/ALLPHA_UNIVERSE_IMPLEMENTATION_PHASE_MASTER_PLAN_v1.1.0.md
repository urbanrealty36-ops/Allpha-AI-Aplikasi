# ALLPHA UNIVERSE --- IMPLEMENTATION PHASE MASTER PLAN

**Versi:** 1.1.0\
**Status:** Reconciled baseline v1.1.0 — Master PRD v3.0.0 + GLB publishing and native spatial UI/UX gates\
**Tujuan:** Menjadi rencana eksekusi engineering terperinci (`ENG-P00`–`ENG-P37`) bagi AI coding agents, engineering, product, design, QA, security, dan release team untuk membangun Allpha dari nol. Master PRD v3.0.0 tetap mendefinisikan roadmap produk (`PRD-P00`–`PRD-P24`); rencana ini tidak menggantikannya.

------------------------------------------------------------------------

### Phase namespace governance

- Product roadmap references use `PRD-Pnn` and follow Master PRD v3.0.0 Part XVIII §82.
- Engineering execution references use `ENG-Pnn` and follow this plan's 00–37 sequencing.
- The [Phase Roadmap Crosswalk](./PHASE_ROADMAP_CROSSWALK.md) records the accepted namespace decision; detailed mapping review remains follow-up.
- ADR-0001 status: `accepted` by explicit Product Owner directive on 2026-10-13. This does not mark Phase 00 complete; ENG-P01 execution is authorized to proceed.

## 1. Mandat Dokumen

Dokumen ini mengubah arah produk pada **Master PRD Allpha Universe
v3.0.0** menjadi urutan implementasi yang dapat dieksekusi. Ini bukan
daftar nama fitur semata. Setiap phase harus menghasilkan kemampuan
produk nyata yang terhubung dari database hingga UI, memiliki kontrol
keamanan, pengujian, dan bukti yang dapat diperiksa.

Allpha dibangun sebagai **AI Social Universe for Humans & AI Agents**:
sebuah jaringan sosial dan dunia digital hidup tempat manusia membangun
identitas, memiliki dan mengatur AI Agent, berinteraksi dengan manusia
dan Agent lain, menerbitkan konten, berkolaborasi, hadir di ruang 3D,
mengikuti pengalaman live, dan berpartisipasi dalam ekonomi kreator.

Allpha bukan sekadar chatbot, aplikasi feed, game metaverse, atau
kumpulan 82 aplikasi terpisah. Domain-domain produk harus menggunakan
engine dan kontrak bersama yang jelas.

### Aturan wajib

1.  **Mulai dari nol.** Bangun aplikasi mobile, web, backend/API, dan
    database baru sesuai PRD. Jangan menjadikan repo, deployment,
    database, skema, atau implementasi lama sebagai dependency.
2.  **Tidak memasukkan PWA sebagai target produk.** Targetnya adalah
    pengalaman mobile dan web yang ditentukan PRD; jangan menambahkan
    PWA sebagai persyaratan arsitektur.
3.  **Satu sumber kebenaran.** Semua state bisnis berasal dari database
    dan API resmi. UI tidak boleh membuat state bisnis palsu atau
    melewati backend.
4.  **Tidak ada fake/mock data untuk membuktikan fitur produksi.**
    Fixture sintetis hanya boleh dipakai dalam unit/integration test
    yang diberi label jelas dan tidak boleh dianggap sebagai bukti
    aktivasi produksi.
5.  **Setiap phase adalah vertical slice yang lengkap.** Minimal
    mencakup:
    -   kontrak requirement dan acceptance criteria;
    -   migrasi/skema database bila diperlukan;
    -   backend/service/engine/API;
    -   UI mobile dan web yang relevan;
    -   integrasi dengan domain yang sudah selesai;
    -   authorization, privacy, isolation, validation, audit, dan rate
        limit sesuai risiko;
    -   unit, integration, API, dan UI tests yang relevan;
    -   dokumentasi operasional serta evidence.
6.  **Selesaikan dependency sebelum mengonsumsi capability-nya.** Jangan
    membuat stub permanen untuk menutupi engine yang belum tersedia.
7.  **Jangan mengklaim GREEN tanpa bukti.** Catat commit/build, hasil
    test, migration status, endpoint/API evidence, screenshot atau
    rekaman UI, log, dan hasil security checks yang relevan.
8.  **Phase terakhir hanya untuk quality gate dan release validation.**
    Tidak boleh menjadi tempat menambahkan fitur baru atau menambal
    desain arsitektur yang belum selesai.
9.  **Tidak ada secret di client.** Semua kredensial, payment
    verification, provider credentials, signing keys, dan operasi
    privileged berada di server-side secret management.
10. **Human owns the Agent.** Otoritas Agent selalu dibatasi oleh izin
    pemilik, kebijakan platform, izin target, anggaran/kuota, dan safety
    policy.
11. **Privasi bersifat default-deny.** Memory, dokumen, percakapan
    privat, kredensial, dan data milik pengguna tidak boleh bocor ke
    pengguna, Agent, komunitas, retrieval corpus, atau model context
    yang tidak berhak mengaksesnya.
12. **Resumable by design.** Workflow/generation yang dapat berlangsung
    lama harus mempunyai checkpoint, status persisten, retry yang aman,
    idempotency, cancellation, dan resume dari titik terakhir yang
    valid.
13. **Tidak menggandakan engine.** Domain menggunakan engine kanonis
    melalui interface; jangan membuat implementasi paralel hanya karena
    fitur muncul pada layar berbeda.
14. **Bahasa produk:** Bahasa Indonesia sebagai bahasa utama, dukungan
    bahasa Inggris, serta kesiapan lokalisasi.
15. **Mobile-first, tetapi bukan mobile-only.** Interaksi utama harus
    nyaman di layar kecil; web tetap memiliki layout dan affordance yang
    sesuai.
16. **Tidak menyebut vendor/model tertentu sebagai ketergantungan
    produk.** Infrastruktur AI didefinisikan secara abstrak melalui AI
    Gateway, Model Router, provider adapter, GPU/cloud/server, storage,
    bandwidth, inference, dan cost controls.

------------------------------------------------------------------------

## 2. Definisi "Phase Selesai"

Sebuah phase baru boleh berstatus **COMPLETE** jika semua hal berikut
terpenuhi.

  -----------------------------------------------------------------------
  Area                                Bukti minimum
  ----------------------------------- -----------------------------------
  Requirement                         Requirement ID, scope, acceptance
                                      criteria, non-goals, dependency,
                                      dan risiko tercatat

  Data                                Schema/migration tervalidasi;
                                      constraint, index, retention, dan
                                      ownership jelas

  Backend                             Service/engine/API nyata;
                                      validation, error contract, auth,
                                      permission, dan audit sesuai
                                      kebutuhan

  UI                                  Screen states loading, empty,
                                      success, error, denied, dan retry;
                                      mobile dan web sesuai scope

  Integrasi                           Alur memakai API resmi dan domain
                                      dependency yang sudah selesai

  Security                            Threat review, authorization tests,
                                      isolation tests, abuse/rate-limit
                                      controls sesuai risiko

  Reliability                         Idempotency, timeout, retry,
                                      cancellation, dan resume bila
                                      relevan

  Tests                               Unit, integration, API contract,
                                      UI, negative-path, dan regression
                                      tests yang relevan lulus

  Observability                       Log terstruktur,
                                      correlation/request ID, metrics,
                                      dan alert yang diperlukan tersedia

  Evidence                            Test reports, migration output, API
                                      evidence, UI evidence, log, dan
                                      commit/build reference tersimpan

  Docs                                Kontrak API, schema, user behavior,
                                      operasi, dan troubleshooting
                                      diperbarui

  Exit gate                           Tidak ada blocker/severity tinggi
                                      yang belum diselesaikan; semua
                                      dependency terverifikasi
  -----------------------------------------------------------------------

Status yang disarankan:
`NOT_STARTED → IN_PROGRESS → BLOCKED (jika perlu) → IN_REVIEW → COMPLETE`.
Status `COMPLETE` bukan sinonim untuk "kode sudah ditulis", "build
lolos", atau "UI terlihat".

### Checklist standar setiap phase

-   [ ] Membaca PRD dan requirement yang terkait.
-   [ ] Memeriksa dependency phase dan kontrak domain.
-   [ ] Menetapkan acceptance criteria yang dapat diuji.
-   [ ] Mendesain perubahan database/API/UI/security sebelum
    implementasi.
-   [ ] Membuat migrasi yang dapat diulang dan aman.
-   [ ] Mengimplementasikan backend/engine dan API resmi.
-   [ ] Menghubungkan UI mobile dan web ke API nyata.
-   [ ] Menguji success, empty, invalid, unauthorized, forbidden,
    timeout, retry, dan failure.
-   [ ] Memastikan tidak ada data lintas-owner yang bocor.
-   [ ] Memastikan observability dan audit tersedia.
-   [ ] Menjalankan tests dan menyimpan evidence.
-   [ ] Memperbarui dokumentasi, dependency map, dan requirement
    traceability.
-   [ ] Memastikan tidak ada TODO/stub/mock pada jalur produksi yang
    diklaim selesai.

------------------------------------------------------------------------

## 3. Peta Dependency Utama

``` mermaid
flowchart TD
  P00[00 Product & Requirement Control] --> P01[01 Platform Foundation]
  P01 --> P02[02 Data, Auth & Authorization]
  P02 --> P03[03 Human Identity]
  P03 --> P04[04 Social Graph]
  P02 --> P05[05 Agent Identity & Passport]
  P05 --> P06[06 Agent Studio & Skills]
  P06 --> P07[07 Knowledge Ingestion & Learning]
  P07 --> P08[08 Memory & Retrieval]
  P01 --> P09[09 AI Gateway & Model Router]
  P05 --> P10[10 Agent Runtime]
  P08 --> P10
  P09 --> P10
  P10 --> P11[11 Durable Workflow Orchestration]
  P06 --> P12[12 Skill Challenge & Evaluation]
  P10 --> P12
  P03 --> P13[13 Content Creation]
  P13 --> P14[14 Feed]
  P13 --> P15[15 Reels & Media]
  P13 --> P16[16 Stories & Moments]
  P14 --> P17[17 Search & Discovery]
  P04 --> P18[18 Messaging]
  P18 --> P19[19 Communities & Collaboration]
  P02 --> P20[20 Notifications]
  P01 --> P21[21 Spatial Domain & Navigation]
  P21 --> P22[22 Theme & Asset Pipeline]
  P22 --> P23[23 World Renderer & Booths]
  P05 --> P24[24 AI Character & Animation]
  P23 --> P25[25 Live Experience]
  P24 --> P25
  P25 --> P26[26 Realtime Streaming]
  P20 --> P27[27 Events & Scheduling]
  P06 --> P28[28 Agent Marketplace]
  P28 --> P29[29 Commerce & Creator Economy]
  P29 --> P30[30 Subscription, Credits & Billing]
  P14 --> P31[31 Advertising & Sponsorship]
  P02 --> P32[32 Trust, Safety & Moderation]
  P03 --> P33[33 Analytics & User Insights]
  P01 --> P34[34 Admin Control Plane]
  P02 --> P35[35 Developer Platform & Interoperability]
  P01 --> P36[36 Observability & AI Evaluation]
  P03 --> P37[37 Final E2E, Regression & Release Gate]
  P10 --> P37
  P14 --> P37
  P23 --> P37
  P26 --> P37
  P30 --> P37
  P32 --> P37
  P34 --> P37
```

Diagram ini menggambarkan dependency utama, bukan larangan menjalankan
pekerjaan paralel. Phase hanya dapat dinyatakan selesai jika dependency
yang dibutuhkan benar-benar siap.

------------------------------------------------------------------------

# 4. Daftar Phase Implementasi dari Nol

## PHASE 00 --- Product Contract, Requirement Traceability & Delivery Governance

**Execution status (2026-10-13):** `in_progress` — initial governance artifacts committed; Phase 00 exit gate is not yet passed. Under ADR-0001, the Product Owner approved the two-namespace approach (PRD-P00–PRD-P24 and ENG-P00–ENG-P37); Engineering Lead approval and detailed crosswalk review remain pending. Repository baseline has only GLB acquisition/readiness workflows confirmed in the workflow directory; no application source tree was present in the root listing at this inspection. This is a limited tree inspection, not proof that every possible application implementation is absent.

**Phase 00 artifacts:**
- [Product Contract, Traceability & Delivery Governance](./PHASE_00_PRODUCT_CONTRACT_TRACEABILITY_GOVERNANCE.md)
- [Requirement Traceability Matrix — 82 domains](./REQUIREMENT_TRACEABILITY_MATRIX.md)
- [ADR and Risk Register](./ADR_AND_RISK_REGISTER.md)
- [Master PRD Section Traceability — 91 numbered sections](./MASTER_PRD_SECTION_TRACEABILITY.md)
- [Phase Execution, Test, Evidence and Release Templates](./PHASE_EXECUTION_TEMPLATES.md)

**Phase 00 evidence/status:** governance package authored and read-back verified; no application test suite or app build was run because the inspected repository root currently exposes `.github/`, `docs/`, `tools/`, `AGENTS.md`, and `README.md`, with two GLB acquisition/readiness workflows. Requirements and domain mapping are drafts awaiting review; ADR-0001 remains open. Do not mark this phase `COMPLETE` until the Phase 00 exit checklist in the governance document is reviewed and signed off.


**Tujuan:** Menetapkan kontrak produk dan cara kerja agar semua AI
coding agents membangun produk yang sama, bukan menafsirkan Allpha
secara berbeda.

**Scope** - Mengurai Master PRD menjadi requirement ID yang unik. -
Memetakan setiap requirement ke domain, engine, data, API, UI, security,
test, evidence, dan phase. - Menetapkan glossary, entity vocabulary,
role, lifecycle status, event taxonomy, error contract, API versioning,
serta definition of done. - Menetapkan keputusan arsitektur awal dan
daftar Architecture Decision Records (ADR). - Menentukan release train,
branch/PR policy, code review, migration policy, dan evidence
registry. - Menetapkan klasifikasi data: public, internal, private,
sensitive, secret, dan system-only. - Menetapkan severity bug, blocker
policy, risk register, serta perubahan requirement.

**Deliverables** - Requirement Traceability Matrix. - Domain/engine
ownership map. - Phase dependency map. - ADR register dan risk
register. - Template phase plan, test plan, evidence report, dan release
report.

**Exit gate** - Tidak ada requirement utama tanpa owner, dependency,
acceptance criteria, dan phase target. - Tidak ada konflik definisi
domain/entitas yang diketahui dibiarkan tanpa keputusan.

## PHASE 01 --- New Platform Foundation & Deployable Thin Slice

**Execution status (2026-10-13):** `in_progress` — branch `feat/eng-p01-platform-foundation`; initial scaffold and CI checks are being implemented. This is not a completion claim.

**Tujuan:** Membuat fondasi aplikasi baru yang dapat dibangun, diuji,
dideploy, dan diobservasi dari awal.

**Scope** - Menyiapkan aplikasi mobile, aplikasi web, backend API,
shared contracts, dan konfigurasi lingkungan. - Menentukan modular
boundaries, dependency rules, API client, design token pipeline,
environment configuration, dan secret management. - Menyiapkan CI/CD,
build checks, lint, type checks, dependency scanning, migration
validation, dan artifact versioning. - Menyediakan health/readiness
endpoint, versi aplikasi, deployment metadata, dan error response
standar. - Menyediakan halaman system status/diagnostics internal yang
hanya menampilkan data nyata dari service. - Menetapkan
dev/test/staging/production configuration separation.

**Deliverables** - Deployable minimal mobile + web + API. - API
health/readiness contract. - CI/CD pipeline dan build artifact yang
dapat ditelusuri. - Environment and secret handling guide.

**Exit gate** - Build bersih dari source baru; deployment dan health
checks terbukti. - Tidak ada credential atau environment secret di
bundle client. - Pipeline gagal dengan benar saat quality check wajib
gagal.

## PHASE 02 --- Database, Authentication, Authorization & Tenant Isolation

**Tujuan:** Menyediakan identitas login dan boundary akses sebagai
fondasi seluruh domain.

**Scope** - Mendesain database baru berdasarkan domain, ownership,
tenant/account boundary, audit, dan lifecycle. - Mengimplementasikan
authentication, session lifecycle, token refresh/revocation, account
recovery, dan logout. - Mengimplementasikan authorization server-side
dengan policy yang dapat diuji; RBAC untuk peran, ABAC untuk
konteks/atribut. - Menetapkan row-level access policies, service-role
isolation, data ownership, dan privileged operation boundaries. -
Menetapkan migration workflow, backup/restore strategy, retention,
deletion, dan schema change policy. - Membuat API error contract untuk
unauthenticated, unauthorized, forbidden, validation failure, dan
conflict.

**Deliverables** - Authenticated API dan client flow. - Role/policy
framework. - Data access policies dan audit baseline. - Migration and
restore runbook.

**Exit gate** - Pengguna A tidak dapat membaca/mengubah data privat
pengguna B. - Role biasa tidak dapat menjalankan operasi privileged. -
Session revocation, recovery, dan negative authorization tests lulus.

## PHASE 03 --- Human Identity, Profile, Settings & Privacy Controls

**Tujuan:** Menyediakan identitas manusia sebagai dasar hubungan sosial
dan kepemilikan Agent.

**Scope** - Registrasi/onboarding, handle, display name, bio, avatar,
profile visibility, language, timezone, preferences, dan account
settings. - Public/private profile, blocked accounts, muted accounts,
visibility controls, consent, data export/delete request. - Profile
preview dan kontrol audience sebelum menerbitkan data. - Ownership model
untuk Agent yang dibuat atau dikelola manusia. - UI mobile dan web untuk
profile, edit profile, privacy, security settings, dan account
lifecycle.

**Deliverables** - Profile API dan database entities. - Profile screens
dan privacy settings. - Owner relationship contract untuk Agent.

**Exit gate** - Visibility settings berlaku di semua API yang
menampilkan profile. - Private fields tidak muncul di search, feed,
public profile, atau API tanpa izin. - Account lifecycle dan consent
events tercatat.

## PHASE 04 --- Social Graph, Follow, Relationship & Interest Graph

**Tujuan:** Membangun graph hubungan yang menjadi fondasi feed,
discovery, rekomendasi, dan komunitas.

**Scope** - Follow/unfollow, friend/connection bila dipakai, block/mute,
relationship state, pending request, dan visibility. - Interest,
passion, habit, goal, context, community, content, knowledge,
reputation, serta interaction signals sebagai graph edges yang
terdefinisi. - Relationship privacy dan graph traversal policy. - Event
untuk perubahan graph yang dikonsumsi recommendation/discovery. - UI
untuk mengikuti akun, melihat relasi, mengelola block/mute, dan mengatur
minat.

**Deliverables** - Social graph API dan policy. - Interest selection and
relationship UI. - Graph event contract.

**Exit gate** - Graph traversal tidak membocorkan relasi privat. -
Follow/block/mute konsisten di profile dan seluruh surface sosial yang
telah tersedia.

## PHASE 05 --- AI Agent Identity, Ownership, Persona & Agent Passport

**Tujuan:** Membuat AI Agent sebagai identitas digital yang nyata, bukan
sekadar chat session.

**Scope** - Create, edit, archive, transfer/disable bila diizinkan, dan
delete Agent sesuai lifecycle policy. - Persona, purpose, tone,
language, profile, capabilities, skill references, avatar/character
references, owner, visibility, status, dan version. - Agent Passport:
identitas, owner disclosure, capability declarations, permission scope,
trust/safety status, provenance, dan audit history. - Agent access
boundary: apa yang boleh dibaca, dibuat, dikirim, atau dijalankan. -
Public Agent profile dan private owner configuration yang dipisahkan
secara eksplisit.

**Deliverables** - Agent identity API/data model. - Agent
creation/editor/profile/passport screens. - Ownership and permission
contract.

**Exit gate** - Tidak ada Agent tanpa owner/system owner yang valid. -
Public passport tidak mengekspos prompt privat, secret, private memory,
atau data owner. - Perubahan capability dan izin tercatat serta dapat
dicabut.

## PHASE 06 --- Agent Studio, Skills, Tools & Capability Governance

**Tujuan:** Memberikan alat untuk membangun dan mengelola kemampuan
Agent dengan izin eksplisit.

**Scope** - Agent Studio untuk persona, instructions, skill
configuration, tool access, output style, budget/limits, test console,
versioning, publish/unpublish, rollback. - Skill registry, schema
input/output, capability declaration, tool contracts, permission scopes,
compatibility, versioning, dan deprecation. - Skill execution policy dan
server-side validation. - Preview/test mode yang jelas terpisah dari
produksi. - Human approval untuk capability berisiko dan perubahan
permission. - Skill catalog internal dan kemampuan berbagi/publikasi
yang tunduk pada moderation.

**Deliverables** - Agent Studio UI. - Skill registry/API dan permission
evaluator. - Versioned Agent configuration.

**Exit gate** - Agent hanya dapat menjalankan skill/tool yang
diizinkan. - Invalid input dan permission denial ditangani dengan
jelas. - Rollback konfigurasi mengembalikan versi yang valid tanpa
merusak history.

## PHASE 07 --- Knowledge Ingestion, Document Processing & Agent Learning

**Tujuan:** Memungkinkan Agent belajar dari sumber yang sengaja
diberikan atau diizinkan oleh pemilik.

**Scope** - Upload/import dokumen dan sumber pengetahuan yang didukung,
metadata, owner, audience, license/consent, dan retention. - Pipeline
parsing, text extraction, chunking, classification, embedding, indexing,
processing status, retry, dan quarantine. - Knowledge corpus privat,
knowledge yang sengaja dipublikasikan, dan knowledge bersama dengan
permission yang berbeda. - Reprocessing saat parser/model/embedding
version berubah. - Source citations/provenance agar jawaban dapat
menautkan ke sumber yang memang boleh diakses. - Hapus dokumen dan
propagasi penghapusan ke chunks, embeddings, caches, derived indexes,
serta job yang tertunda. - Progress, failure details yang aman, retry,
dan cancel pada UI.

**Deliverables** - Ingestion pipeline dan job lifecycle. - Knowledge
library UI. - Source/provenance metadata.

**Exit gate** - Dokumen hanya bisa diproses dan dicari oleh principal
yang berhak. - Penghapusan sumber menghapus/menonaktifkan turunan sesuai
policy. - Jawaban berbasis knowledge menampilkan provenance saat
tersedia dan tidak mengarang kutipan.

## PHASE 08 --- Agent Memory, Retrieval, Context Assembly & Privacy Isolation

**Tujuan:** Membuat memori Agent persisten, terstruktur, dapat
dikendalikan pemilik, dan terisolasi.

**Scope** - Working, episodic, semantic, procedural, dan long-term
memory dengan lifecycle yang sesuai. - Hybrid retrieval: semantic/vector
search dan lexical/full-text search; filtering wajib berdasarkan owner,
tenant, permission, audience, retention, dan source status. - Context
assembly dengan token/budget limits, relevance ranking, freshness,
deduplication, provenance, dan policy filtering. - Memory inspect, pin,
correct, forget, export, delete, dan consent controls untuk owner. -
Distinction antara memory privat owner, memory sesi, knowledge corpus,
dan knowledge yang memang dipublikasikan. - Context firewall untuk
mencegah retrieval lintas-owner, lintas-tenant, dan lintas-audience. -
Memory compaction/summarization dengan provenance dan kontrol kualitas.

**Deliverables** - Memory service/API dan retrieval policy. - Owner
memory management UI. - Isolation tests dan deletion propagation tests.

**Exit gate** - Retrieval lintas-owner/tenant gagal pada server-side
tests. - Owner dapat melihat, mengoreksi, dan menghapus memori sesuai
haknya. - Memory yang sudah dihapus tidak kembali lewat cache atau index
aktif.

## PHASE 09 --- AI Gateway, Model Router, Provider Adapters & Cost Policy

**Tujuan:** Menyediakan jalur AI terpusat yang dapat diaudit, diukur,
dibatasi, dan dialihkan tanpa mengikat produk ke satu vendor.

**Scope** - AI Gateway dengan authentication, policy enforcement,
request normalization, response normalization, timeout, retry,
cancellation, dan provider adapters. - Model Router berdasarkan task,
capability, quality tier, privacy classification, latency, availability,
budget, region, modality, dan policy. - Prompt/template versioning,
structured output validation, tool-call validation, safety filters, dan
content handling. - Usage metering: input/output units, duration,
modality, estimated/actual cost, cache usage, and attribution. - Quota,
per-user/per-Agent budget, concurrency, rate limit, circuit breaker,
fallback policy, and provider health. - Data minimization: hanya
mengirim konteks yang dibutuhkan dan diizinkan. - Server-side secret
handling, redaction, and audit. - Provider-independent contracts; jangan
menanam nama model/provider ke domain business logic.

**Deliverables** - AI Gateway API/service. - Model Router policy
engine. - Usage and cost ledger events. - Provider adapter test harness.

**Exit gate** - Semua AI calls produk melewati gateway. - Tidak ada
credential provider di client. - Router dapat menolak permintaan yang
tidak berizin/di luar budget dan mengukur penggunaan. - Failure/fallback
tidak menggandakan transaksi atau mengulang side effect tanpa
idempotency.

## PHASE 10 --- Agent Runtime, Tool Execution & Conversation Sessions

**Tujuan:** Menjalankan Agent secara konsisten dalam konteks percakapan,
tugas, dan surface produk.

**Scope** - Runtime state machine, session, turn, run, tool call,
artifact, trace, and result. - Agent response generation melalui AI
Gateway, memory retrieval, knowledge access, skill/tool invocation, and
safety checks. - Streaming text/status bila didukung oleh transport yang
ditetapkan. - Run states: queued, running, waiting_for_input/approval,
completed, failed, cancelled, and expired. - Budget and permission
enforcement sebelum dan selama eksekusi. - Human handoff, clarification,
confirmation untuk side effects, serta safe failure. - UI chat/session
untuk berinteraksi dengan Agent; jangan menjadikan chat sebagai
satu-satunya interface Agent.

**Deliverables** - Agent Runtime API. - Conversation/session UI. - Run
trace dan error/retry surface.

**Exit gate** - Runtime selalu menerapkan owner policy dan capability
permissions. - Run status konsisten di database, API, UI, dan logs. -
Tool side effects memerlukan permission dan confirmation sesuai risk
policy.

## PHASE 11 --- Durable Workflow Orchestration, Checkpoint & Resume

**Tujuan:** Mendukung workflow panjang dan multi-step yang dapat
dilanjutkan setelah interupsi tanpa mengulang seluruh proses.

**Scope** - Workflow definition, node/edge schema, versioning,
validation, run state, and execution history. - Node families: trigger,
AI task, prompt/template, retrieval, condition, transform, tool/API,
human approval, wait, schedule, notification, media processing, publish,
and terminal nodes. - Checkpoint setelah step yang aman; durable
input/output references; retry policy; idempotency keys;
compensation/rollback untuk side effect yang didukung. -
Pause/resume/cancel, timeout, retry from failed node, replay with
explicit safety restrictions, and dead-letter handling. - Workflow
concurrency, budget, permission propagation, secrets isolation, and run
ownership. - Workflow Builder UI, node configuration forms, validation
messages, execution timeline, logs, and resume controls. - Workflow
execution must be durable; browser tab closure must not silently erase
server-side progress.

**Deliverables** - Workflow engine and node contract registry. -
Workflow Builder and run inspector. - Durable checkpoint storage and
recovery runbook.

**Exit gate** - Interruption/restart test resumes from last valid
checkpoint. - Duplicate delivery does not create duplicate side
effects. - Permission changes are re-evaluated before resumed privileged
actions.

## PHASE 12 --- Skill Challenge, Agent Evaluation, Achievements & Rewards

**Tujuan:** Menguji kemampuan Agent dan memberi reward berdasarkan hasil
yang tervalidasi.

**Scope** - Challenge types such as Message, Ask, Generate, and
domain-specific tasks. - Challenge definition, rubric, test cases,
attempts, evaluation, score, evidence, achievement, and leaderboard
privacy. - Evaluation against explicit criteria; human review for
disputed/high-impact outcomes. - Rewards/credits eligibility, issuance
ledger, caps, expiry, fraud checks, and appeal. - Agent skill
level/version history and public badges that disclose no private
evaluation data. - Anti-cheat: replay detection, collusion signals,
duplicate accounts, and suspicious reward patterns.

**Deliverables** - Challenge and evaluation engine. - Challenge UI and
results. - Reward eligibility and ledger contract.

**Exit gate** - Score/reward is derived from a traceable evaluation. -
No reward can be minted by a client-side claim alone. - Disputes, failed
evaluation, and suspected fraud have defined outcomes.

## PHASE 13 --- Content Creation, Media Pipeline & Content Capsule

**Tujuan:** Menyediakan satu content object model yang digunakan
konsisten oleh Feed, Reels, Stories, Live replay, and Universe surfaces.

**Scope** - Content types: text, image, video, audio, link, poll,
document, generated content, carousel, spatial object/media surface, and
Content Capsule. - Draft, edit, preview, publish, schedule, archive,
delete, report, and visibility lifecycle. - Media upload pipeline,
metadata, validation, transcoding/derivatives, thumbnail, storage
permissions, signed access where appropriate, and cleanup. -
Attribution/provenance for AI-generated content and source/license
metadata where required. - Audience controls, comments policy, tags,
mentions, topic, location/world references, alt text/captions, and
accessibility. - Content Capsule as a portable, structured unit for an
idea, moment, knowledge item, or experience, with version and access
policy. - Client UI for compose, preview, upload progress, retry, draft
recovery, and publishing status.

**Deliverables** - Canonical content schema/API. - Media processing
jobs. - Composer and Content Capsule UI.

**Exit gate** - Content publication cannot bypass moderation/visibility
rules. - Failed upload can retry without duplicate content. -
Deleted/private media is not accessible through stale public URLs or
unauthorized API calls.

## PHASE 14 --- Social Feed, Ranking, Interactions & Feed Controls

**Tujuan:** Membangun home feed yang relevan dan dapat dikendalikan
pengguna.

**Scope** - Feed candidates from followed humans/Agents, communities,
selected topics, and allowed discovery sources. - Ranking with
explainable signals: relevance, freshness, relationship, user
preferences, quality, diversity, and safety. - Like/react, comment,
reply, save, share, repost where allowed, hide, report, and feedback
controls. - Pagination/infinite loading with stable cursor semantics,
deduplication, refresh, and stale-state handling. - Feed settings:
following-first, topic controls, muted sources, sensitive content
controls, and recommendation feedback. - Distinguish organic content,
sponsored content, and system announcements. - Mobile and web feed cards
with loading, empty, error, offline/timeout messaging, and retry.

**Deliverables** - Feed API and ranking contract. - Feed UI and
interaction API. - Recommendation feedback events.

**Exit gate** - Feed respects block, mute, visibility, moderation, and
content deletion. - Ranking is observable and can be debugged without
exposing private signals. - Sponsored placement is clearly labeled and
not disguised as organic content.

## PHASE 15 --- Reels, Short Video, Audio & Media Consumption

**Tujuan:** Menyediakan short-form media experience yang terintegrasi
dengan content model, creator identity, and safety.

**Scope** - Reels/short video/audio surfaces, playback lifecycle,
captions/subtitles, accessibility, creator attribution, and related
content. - Playback prefetch/cache policy, adaptive media delivery,
retry, and bandwidth-aware behavior. - Like/comment/save/share/report
and content-level privacy controls. - Creation/publishing from existing
media pipeline; avoid duplicating a second independent content
backend. - Usage analytics that respect privacy policy. - Safe autoplay
behavior, mute/unmute, pause/resume, and reduced-motion controls.

**Deliverables** - Reels API/query and media playback UI. - Creator
attribution and interaction wiring. - Media performance metrics.

**Exit gate** - Playback failure and retry work on mobile and web. -
Content permissions/moderation apply identically to other content
surfaces. - No media surface exposes unauthorized original files.

## PHASE 16 --- Stories, Moments, Live Updates & Temporary Content

**Tujuan:** Mendukung konten temporer dan update sosial berbasis waktu.

**Scope** - Story/Moment creation, media attachments, audience list,
expiration, archive/keep rules, reactions, replies, and report. -
Expiration scheduler and cleanup policy; archived content has explicit
access rules. - Story sequence and progress, seen state, mute/hide
controls, and privacy-aware viewer list if supported. - Live updates
from Agents or experiences only when owner has authorized publication. -
Expiration must be enforced by API/database policy, not merely by hiding
a UI card.

**Deliverables** - Story/Moment lifecycle API. - Story viewer/creator
UI. - Expiration and cleanup jobs.

**Exit gate** - Expired content is unavailable to unauthorized viewers
and normal queries. - Audience permissions are checked at read time. -
Cleanup and archive behaviors are tested.

## PHASE 17 --- Search, Discovery, Trends & Recommendations

**Tujuan:** Membantu pengguna menemukan manusia, Agent, konten,
komunitas, skills, events, worlds, and booths.

**Scope** - Unified search with entity types, filters, ranking,
pagination, and safe previews. - Search indexing and incremental
updates/deletion propagation. - Interest graph signals and personalized
discovery with controls to reset/adjust interests. - Trends and topic
pages based on eligible aggregated signals; minimum thresholds and
anti-manipulation. - Recommendation explanations at an appropriate level
and "not interested" feedback. - Privacy-aware autocomplete and
suggestion behavior. - Moderation, block, hidden content, and private
entity filters applied before returning results.

**Deliverables** - Search/discovery API and indexing jobs. - Search,
explore, topic, and trend UI. - Recommendation controls and feedback
pipeline.

**Exit gate** - Deleted, blocked, private, and unauthorized entities do
not leak through index results. - Trends have abuse protections and are
not treated as proof of truth. - Search indexing can recover from failed
jobs without duplicate or stale records.

## PHASE 18 --- Messaging, Agent-to-Human & Agent-to-Agent Communication

**Tujuan:** Menyediakan komunikasi privat yang memiliki kontrol akses,
delivery state, and abuse handling.

**Scope** - One-to-one and group conversations, participant roles,
message lifecycle, attachments, replies, reactions, read/delivery status
where appropriate. - Human↔Human, Human↔Agent, and policy-controlled
Agent↔Agent communication. - Agent messaging identity disclosure, owner
permission, recipient policy, and tool boundary. - Realtime delivery
with durable persistence, reconnect, deduplication, and sync after
reconnect. - Message requests, block/report, spam throttling, rate
limits, and retention policy. - Search within authorized conversations,
notification integration, and attachment access policy. - Clear
distinction between message draft, sent, delivered, failed, and deleted
states.

**Deliverables** - Messaging APIs and realtime contracts. -
Inbox/conversation UI. - Message abuse controls and delivery
diagnostics.

**Exit gate** - Conversation membership is verified server-side on every
read/write. - Reconnect does not duplicate messages or lose acknowledged
messages. - Agent cannot message a recipient or perform an action
outside its permissions.

## PHASE 19 --- Communities, Collaboration, Missions & Shared Workspaces

**Tujuan:** Menyediakan ruang sosial dan kerja bersama bagi manusia dan
Agent.

**Scope** - Community creation, public/private access, membership,
roles, rules, topics, moderation, pinned resources, and membership
lifecycle. - Shared tasks, missions, collaborative challenges,
assignments, deadlines, and progress. - Shared Agent access only through
explicit grants, scopes, expiry, and revocation. - Shared
knowledge/resources must retain source ownership and audience
restrictions. - Community feed, discussion, files, events, and agent
participation policies. - Community governance, reports, appeals, and
owner/moderator tools.

**Deliverables** - Community and collaboration APIs. -
Community/workspace UI. - Shared-access grant/revoke contract.

**Exit gate** - Removed members lose access immediately according to
policy. - Private resources cannot be retrieved through Agent memory or
search after access revocation. - Community moderation actions are
auditable.

## PHASE 20 --- Notification Center, Preferences & Delivery Orchestration

**Tujuan:** Mengantarkan notifikasi relevan secara konsisten tanpa
membocorkan informasi privat.

**Scope** - Notification event schema, in-app inbox, read/unread,
grouping, deduplication, preference center, mute windows, and delivery
status. - Triggers from messaging, social graph, content, challenges,
communities, events, commerce, billing, security, and Agent workflows. -
Channel adapters as permitted by product decisions, with opt-in/consent
and user preferences. - Rate limits, digest options, retry, dead-letter
handling, and delivery observability. - Deep links must re-check access
when opened; notification payload must not reveal private content. -
User controls for categories, urgency, and quiet periods.

**Deliverables** - Notification service and event contract. -
Notification center/settings UI. - Delivery retry and deduplication
mechanism.

**Exit gate** - Duplicate events do not create uncontrolled duplicate
notifications. - Revoked/private content is not exposed in notification
previews. - Delivery preference and consent are enforced server-side.

## PHASE 21 --- Spatial Domain Model, Universe Hierarchy & Navigation

**Tujuan:** Menetapkan struktur dunia digital yang dapat dinavigasi dan
direpresentasikan secara konsisten.

**Scope** - Canonical hierarchy: Universe/Galaxy → World → District →
Zone → Booth/POI → scene object/media surface. - Ownership, permissions,
public/private visibility, capacity, discovery metadata, theme
reference, version, lifecycle, and moderation. - World/District maps,
coordinate systems, scale/units, spawn points, entrances/exits,
landmarks, navigation nodes, paths, and collision/navigation metadata. -
Spatial presence, visit/session lifecycle, location state, and event
contracts. - Navigation search, waypoint/pathfinding contract,
arrival/interaction radius, and fallback for unsupported devices. -
Spatial object identity and reference contracts so that content, ads,
events, and Agents can be placed without creating duplicate object
models.

**Deliverables** - Spatial domain API and database model. -
Universe/world/district navigation screens. - Spatial graph and
coordinate conventions.

**Exit gate** - A real persisted Universe/Galaxy, World, District, and
POI can be created and retrieved through official APIs. - Parent/child
relationships and spatial coordinates are validated. - Access
restrictions are enforced for private worlds and zones.

## PHASE 22 --- Theme Builder, 3D Asset Pipeline & Asset Governance

**Tujuan:** Menyediakan pipeline aset 3D yang aman, versioned,
performant, and publishable.

**Scope** - Theme templates, asset categories, versioning, manifests,
licensing/provenance, moderation, compatibility, and publishing
lifecycle. - Asset ingest, validation, malware/content checks where
applicable, format/metadata checks, geometry/material checks, bounds,
scale, texture budget, animation/rig contract, and compression. - Asset
manifests with immutable identifiers, checksums, file size, dimensions,
and references. - Storage access policies and signed access where
required; no assumption that "file exists" means "approved for
publication". - Theme/World Builder UI to assemble scenes from approved
assets and configure lighting, materials, environment, and object
placement. - Asset review states, rejection reasons, replacement/version
rollback, and deprecation. - Device performance tiers and asset
variants; avoid forcing every device to download every high-detail
asset.

**Deliverables** - 3D asset pipeline and manifest contract. -
Theme/World Builder UI. - Asset moderation and publish lifecycle.

**Exit gate** - Only validated, licensed/authorized, approved assets can
be used in published scenes. - Manifest checksum/size matches the actual
stored object. - Failed asset processing is recoverable and does not
silently publish partial assets.

## PHASE 23 --- World Renderer, Districts, Buildings, Booths & Spatial Interaction

**Tujuan:** Merender dunia 3D yang dapat dijelajahi dan berinteraksi
dengan object nyata dari backend.

**Scope** - Renderer integration and scene lifecycle; asset loading,
progressive loading, LOD/quality tiers, culling, memory cleanup, and
fallback. - Districts with streets, buildings, landmarks, portals,
public areas, and points of interest. - Booth/Tenant spaces with
ownership, content, products/services, schedule, visit action, and
moderation policy. - Spawn/teleport/portal, movement controls,
collision/pathfinding, interaction prompts, and accessible navigation
alternatives. - Object interaction contracts for profile, Agent,
content, booth, event, and commerce. - Billboard/videotron/media
surfaces connected to authorized content and advertising placements. -
Scene state synchronization and graceful recovery after asset/network
failure. - Device profiling and performance budgets for mobile and
desktop.

**Deliverables** - Functional World/District/Booth renderer. -
Navigation and interaction UI. - Performance diagnostics and fallback
behavior.

**Exit gate** - Real published scene data and approved assets render
from official API/manifest. - Unauthorized/private objects are not
fetched or shown. - Renderer handles missing assets, slow network, and
device constraints without crashing.

## PHASE 24 --- Human Avatars, AI Characters, Uniforms & Animation Contract

**Tujuan:** Memberi identitas visual pada manusia dan Agent dengan
capability yang jujur terhadap rig dan asset yang tersedia.

**Scope** - Human avatar/profile visual and AI Character assignment. -
Character asset metadata, rig/skeleton compatibility, animation clips,
facial blendshapes, eye movement, mouth/lip sync, hand gestures,
full-body movement, and expression capabilities. - Uniform/cosmetic
inventory, entitlement, ownership, preview, equip/unequip, and
moderation. - Animation contract: required/optional channels, supported
skeleton, retargeting rules, fallback animations, and capability
validation. - Character safety and impersonation policy; disclose AI
identity and prevent misleading human likeness where prohibited. - Asset
loading, animation state machine, interruption handling, and
reduced-motion settings.

**Deliverables** - Character/Avatar service contracts. -
Character/uniform selection UI. - Rig and animation capability registry.

**Exit gate** - UI never advertises animation capability unsupported by
the asset/rig. - Character ownership/entitlement is checked
server-side. - Failed animation/asset loading falls back safely and
predictably.

## PHASE 25 --- Live Experience, Virtual Stage & Presentation Tools

**Tujuan:** Menyediakan ruang pengalaman live yang bisa dipakai untuk
podcast, talkshow, presentation, pitching, news, product marketing,
classroom, mentor room, and tutor room.

**Scope** - Stage templates, host/guest roles, capacity, session
lifecycle, scheduling reference, scene configuration, and permissions. -
AI Character as presenter, tutor, interviewer, mentor, podcast host,
news host, or product presenter within configured policy. -
Document/PDF/slide ingestion and presentation surfaces, page/slide
navigation, presenter notes with access controls, and synchronized
audience view. - Scene layouts, stage media surfaces, screen sharing
where supported, audience interaction, Q&A, polls, and moderation. -
Stage recording/replay policy, consent, retention, content rights, and
publication flow. - Host controls, hand-raise/speaker permissions,
mute/removal, waiting room, and incident handling.

**Deliverables** - Live Experience and Stage APIs. - Stage creation/join
UI and presentation controls. - Stage templates and capability
contracts.

**Exit gate** - Host/guest/audience permissions are enforced. -
Presentation assets respect access/retention policy. - Stage can be
created, joined, moderated, and closed through real product flows.

## PHASE 26 --- Realtime Streaming, Voice, Dual Camera & Live Animation

**Tujuan:** Mengaktifkan komunikasi realtime yang menggabungkan manusia,
AI voice, character animation, and stage state.

**Scope** - Realtime transport/session signaling, participant lifecycle,
reconnect, quality telemetry, and session cleanup. - Separate Human
Camera and AI Virtual Camera concepts; source selection, permission
prompts, preview, mute, camera switching, and explicit consent. - AI
voice interaction, interruption/barge-in behavior, turn-taking, latency
budgets, voice session states, and failure fallback. - Animation
synchronization: voice activity, lip sync, face/eyes, gestures, hands,
and full-body animation where supported. - Stream recording/relay
policy, privacy, access control, bandwidth adaptation, and
regional/system capacity controls. - Human and AI participants are
distinguishable; Agent cannot activate camera/microphone or broadcast
beyond explicit permission. - Realtime failure states, reconnection,
fallback to audio/text, and host controls.

**Deliverables** - Realtime session/participant contracts. - Live room
UI and device permission flows. - Voice/animation synchronization
integration.

**Exit gate** - Camera/microphone access requires explicit permission. -
Disconnect/reconnect preserves session consistency and prevents
duplicate participants. - AI voice/animation capabilities are bounded by
the actual character and transport contract.

## PHASE 27 --- Events, Scheduling, Attendance & Experience Lifecycle

**Tujuan:** Menghubungkan pengalaman spatial/live dengan event yang
dapat ditemukan, diikuti, dan dikelola.

**Scope** - Event creation, host, description, time zone, start/end,
capacity, access policy, registration, waitlist, reminders, attendance,
cancellation, and reschedule. - Events can reference a World, District,
Booth, Stage, community, or Agent. - Calendar/list discovery, event
detail, join flow, attendance state, and post-event content. - Time-zone
correctness, recurrence rules if supported, conflict validation, and
idempotent reminder scheduling. - Event safety, host trust, age/access
restrictions where required, and report/moderation workflow.

**Deliverables** - Event/scheduling API. - Event
browse/detail/create/manage UI. - Attendance and reminder contracts.

**Exit gate** - Time and capacity rules are enforced server-side. -
Cancel/reschedule propagates to reminders and participants. - Join
access is revalidated at event start.

## PHASE 28 --- Agent Catalog, Marketplace & Service Discovery

**Tujuan:** Memungkinkan pengguna menemukan Agent, skills, workflows,
templates, and services dengan trust dan compatibility yang jelas.

**Scope** - Catalog entries, category, tags, version, owner, capability,
requirements, pricing/entitlement reference, rating/review eligibility,
moderation, and deprecation. - Install/enable/use flow with explicit
permission summary. - Compatibility checks for skills, runtime, tools,
and policy. - Search/filter/sort, detail page, changelog, version
pinning, report, and uninstall/revoke. - Clear distinction between
listing, installed capability, permission grant, and actual usage. -
Seller/creator identity and provenance.

**Deliverables** - Catalog/marketplace APIs. - Discovery, detail,
install/enable UI. - Permission review and version compatibility flow.

**Exit gate** - Listing a capability does not automatically grant its
permissions. - Removed/deprecated unsafe items cannot be newly
installed. - Reviews/ratings are tied to eligible, non-fraudulent
interactions.

## PHASE 29 --- Commerce, Booth Tenant, Creator Economy & Revenue Sharing

**Tujuan:** Mengaktifkan transaksi produk/jasa digital dan fisik yang
disetujui, termasuk monetisasi kreator dan tenant.

**Scope** - Product/service listings, offers, order lifecycle,
inventory/availability where applicable, delivery/fulfillment
references, refunds/cancellations, disputes, and seller dashboard. -
Booth tenant pages, catalog, booking/purchase action, business profile,
and operational status. - Creator monetization, paid content/experience,
tips or support, revenue share, commissions, settlement eligibility, and
creator statements. - Ledger-based accounting: immutable entries,
balanced movements, adjustments, reversal, idempotency, and
reconciliation. - Taxes/fees are configurable by jurisdiction/business
policy; do not hardcode unsupported legal assumptions. - Fraud controls,
seller verification, abuse handling, and dispute audit trail.

**Deliverables** - Commerce/order/ledger contracts. - Booth commerce and
creator earnings UI. - Settlement/reconciliation reports.

**Exit gate** - Financial changes are ledgered and auditable. - Client
cannot mark an order paid or mint a creator balance. - Refund/reversal
preserves the original transaction trail.

## PHASE 30 --- Freemium, Subscription, AI Credits, Billing & Payment Settlement

**Tujuan:** Menyediakan monetisasi platform dan pembatasan penggunaan
yang transparan serta dapat direkonsiliasi.

**Scope** - Free/Premium/Enterprise entitlement definitions, quotas,
limits, feature access, reset periods, grace period, renewal,
cancellation, and downgrade behavior. - AI Credits wallet and ledger;
top-up, consumption, reservation/release, expiry, reward issuance,
refunds, and adjustments. - Usage metering from AI, media, storage,
bandwidth, live sessions, and other billable dimensions defined by
product policy. - Pricing catalog, invoice/receipt, tax/fee
representation where applicable, payment initiation,
signed/server-verified payment notifications, settlement, refund, and
reconciliation. - Payment gateway adapter abstraction; client never
controls payment truth. - Subscription lifecycle, entitlement cache
invalidation, payment failure recovery, duplicate webhook protection,
and dispute handling. - Spend limits, low-credit warnings, budget
policies, and hard/soft limits. - Separate creator reward credits from
platform revenue and cash payable until the accounting policy says
otherwise.

**Deliverables** - Entitlement/billing/credit services. - Pricing,
wallet, subscription, transaction history, and invoice UI. - Payment
webhook and reconciliation runbook.

**Exit gate** - Entitlements follow verified billing state. - Duplicate
payment notifications cannot double-credit. - Credit balance matches
ledger and is not client-editable. - Failed/cancelled/refunded payments
have defined entitlement and ledger outcomes.

## PHASE 31 --- Advertising, Sponsorship & Spatial Ad Inventory

**Tujuan:** Menyediakan monetisasi iklan yang transparan, terukur, dan
tidak merusak kepercayaan pengguna.

**Scope** - Campaign, advertiser, creative, placement, audience
eligibility, budget, schedule, frequency cap, status, review, and
reporting. - Sponsored feed placements, billboard/videotron surfaces,
booth sponsorship, event sponsorship, and other explicitly supported
inventory. - Ad disclosure labels, targeting consent/preferences,
sensitive category restrictions, brand safety, and frequency control. -
Impression/click/viewability event definitions and deduplication. -
Budget reservation, spend ledger, pacing, campaign pause, invalid
traffic detection, and advertiser billing references. - Separation
between organic recommendation ranking and paid placement; ads must not
be disguised as organic content. - Advertiser/agency roles and approval
workflow.

**Deliverables** - Ad campaign and placement API. - Advertiser
management UI and ad disclosure UI. - Impression/spend measurement
contract.

**Exit gate** - Every paid placement is labeled. - Targeting respects
consent and restrictions. - Spend and impression counts are auditable
and protected against obvious replay/fraud.

## PHASE 32 --- Trust, Safety, Moderation, Reputation & Anti-Fraud

**Tujuan:** Menyatukan policy enforcement lintas identitas, konten,
Agent, messaging, live, spatial, marketplace, and commerce.

**Scope** - Report, moderation case, triage, review, decision, appeal,
enforcement, expiry, and audit. - Policy engine for content, Agent
behavior, tool use, live sessions, marketplace listings, ads, and
commerce. - Spam, impersonation, harassment, fraud, coordinated
manipulation, reward abuse, payment abuse, malicious uploads, and unsafe
automation signals. - Human review queues, evidence retention, moderator
roles, conflict-of-interest controls, and appeal workflow. - Reputation
signals with clear provenance and anti-gaming controls; reputation must
not silently become an unrestricted authority grant. - Safety state
propagation: blocked/suspended/deleted entities are handled across feed,
search, messages, events, world, catalog, and billing. - User controls
for block, mute, restrict, report, and safety preferences.

**Deliverables** - Trust/safety policy engine and moderation case
system. - User report and moderator review UI. - Cross-domain
enforcement event contract.

**Exit gate** - Enforcement propagates across all integrated surfaces. -
Moderator actions are permissioned and audited. - Appeal and reversal
are supported without erasing the original decision history.

## PHASE 33 --- Analytics, Insights & Product Intelligence

**Tujuan:** Memberikan metrik yang membantu pengguna, kreator, tenant,
dan operator mengambil keputusan tanpa membocorkan data yang tidak
berhak mereka lihat.

**Scope** - User-facing activity/Agent usage insights, creator
performance, content performance, booth/event performance, campaign
metrics, and usage/cost reports. - Event taxonomy, attribution rules,
aggregation windows, retention, sampling, and deduplication. - Data
access tiers: user-owned, creator-owned, tenant-owned, advertiser-owned,
operator aggregate, and restricted system metrics. - Privacy-preserving
aggregation, minimum cohort thresholds where needed, export controls,
and data minimization. - Dashboard filters and definitions so the same
metric is not computed differently across screens. - Separate
operational telemetry from business analytics and from AI evaluation
datasets.

**Deliverables** - Analytics event schema and aggregation pipeline. -
Role-scoped dashboards and exports. - Metric dictionary and lineage
documentation.

**Exit gate** - Users see only metrics they are authorized to access. -
Key metrics have documented definitions and lineage. - Analytics events
do not contain secrets or unnecessary raw private content.

## PHASE 34 --- Super Admin Control Plane, Governance & Operations

**Tujuan:** Menyediakan operasi platform yang aman tanpa memberi admin
akses tak terbatas secara default.

**Scope** -
User/Agent/content/world/asset/marketplace/ad/event/commerce/credit/subscription/moderation
management. - Search and inspect operational entities with privacy-aware
masking and access reasons. - Role/permission administration, feature
flags, system configuration, policy versioning, rollout, rollback,
maintenance mode, and incident controls. - Transaction explorer, audit
explorer, moderation queues, asset approval, data correction workflows,
and operational reports. - High-risk actions require step-up
authentication/approval, reason capture, audit, and safe confirmation. -
Admin "view as" or support access, if allowed, must be time-bound,
scoped, disclosed/audited, and not silently bypass privacy. -
Configuration changes have validation, preview, version, audit, and
rollback.

**Deliverables** - Super Admin UI and APIs. - Governance policy and
privileged action audit. - Operational runbooks.

**Exit gate** - Admin APIs enforce explicit permission checks. -
High-risk operations cannot be performed through hidden UI-only
controls. - Every privileged mutation has actor, reason, target,
timestamp, and outcome recorded.

## PHASE 35 --- Developer Platform, Public API & Agent Interoperability

**Tujuan:** Membuka integrasi terkontrol bagi developer dan Agent
eksternal tanpa melemahkan trust boundary.

**Scope** - Developer registration, app/project, API keys or equivalent
credentials, OAuth/client authorization where applicable, scopes,
quotas, rotation, revocation, and audit. - API catalog, versioning,
schema documentation, examples, sandbox/test environment, webhook
registration, delivery retry, and signature verification. -
Agent-to-Agent interoperability contracts, identity disclosure,
capability negotiation, consent, permissions, and rate limits. - Data
export/import contracts, webhook privacy, idempotency, and replay
protection. - SDK/client generation only from canonical API contracts;
no secret embedded in public client. - App review and risk tiering for
high-impact scopes.

**Deliverables** - Developer portal and API documentation. -
Credential/scope management. - Webhook and interoperability contract
tests.

**Exit gate** - Revoked credentials stop working. - API scopes are
enforced server-side. - Webhook signature, retry, replay, and
idempotency behavior is tested.

## PHASE 36 --- Observability, Reliability, AI Evaluation & Cost Operations

**Tujuan:** Menjadikan sistem dapat dipantau dan diperbaiki berdasarkan
bukti operasional, bukan tebakan.

**Scope** - Structured logs, trace/correlation IDs, metrics, service
health, queue depth, job latency, error rates, saturation, and alert
routing. - AI quality evaluation: task success, groundedness/provenance,
policy adherence, latency, cost, tool success, refusal correctness, and
regression suites. - Provider/adapter health, fallback frequency, budget
burn, token/unit usage, storage/bandwidth, live quality, and queue
costs. - SLO/SLI definitions for critical journeys and services; error
budgets and incident severity. - PII/secret redaction, access controls
for logs, retention, sampling, and audit. - Incident management,
runbooks, rollback, disaster recovery, backup restore tests, and
post-incident review. - Evaluation datasets are consented/authorized,
privacy-reviewed, and separated from production private memory.

**Deliverables** - Operational dashboards and alerts. - AI evaluation
harness and regression datasets. - SLO and incident runbooks.

**Exit gate** - Critical failure modes have observable signals and
actionable alerts. - AI/runtime changes can be evaluated against
repeatable criteria. - Backup/restore and incident procedures are
tested, not merely documented.

## PHASE 37 --- Final Cross-Domain E2E, Security Regression & Release Validation

**Tujuan:** Membuktikan bahwa seluruh phase yang telah dinyatakan
selesai bekerja sebagai satu produk, aman, konsisten, dan siap dirilis.

**Batasan keras:** Phase ini **tidak boleh menambahkan fitur baru**.
Jika ditemukan fitur yang belum diimplementasikan, buat backlog/phase
correction yang jelas; jangan menyamarkan pekerjaan implementasi sebagai
QA.

**Scope** - End-to-end critical journeys menggunakan data uji yang
disiapkan secara eksplisit dan lingkungan yang benar. - Auth → human
profile → create Agent → configure skills → ingest knowledge → retrieve
private memory → execute Agent → resume workflow. - Create content →
feed/reels/story → discovery/search → message/community →
notification. - Create Universe/World/District/Booth → approve asset →
render scene → interact with Agent/content/event. - Create live stage →
join session → use presentation → test human camera and AI virtual
camera → disconnect/reconnect → close/replay according to policy. -
Marketplace listing → install with permission →
commerce/credits/subscription → verified
payment/ledger/reconciliation. - Ad campaign → approved placement →
labeled impression → spend reporting. - Report/moderation → enforcement
propagation → appeal/reversal. - Admin action → authorization/audit →
rollback if supported. - Cross-owner and cross-tenant isolation, IDOR,
privilege escalation, prompt/context injection, secret leakage, webhook
replay, race conditions, and abuse tests. - Mobile and web
compatibility, responsive behavior, accessibility, localization,
performance, low-bandwidth behavior, and graceful degradation. - Full
regression, load/stress/soak tests as appropriate, backup/restore
verification, migration verification, and release candidate smoke
tests. - Release checklist, known limitations, rollback plan, monitoring
plan, and sign-off evidence.

**Deliverables** - Cross-domain E2E report. - Security/privacy
regression report. - Performance/accessibility report. - Release
candidate and rollback evidence. - Final requirement traceability
status.

**Exit gate** - All critical journeys pass with real backend/API
integration. - No open critical/high-severity security issue without
formally approved mitigation. - No data isolation failure,
payment/credit ledger inconsistency, or unrecoverable workflow
failure. - All release-blocking tests pass and evidence is attached. -
Product, engineering, security, and release owners sign off against the
same checklist.

------------------------------------------------------------------------

# 5. Critical End-to-End Journeys

Phase completion should be evaluated against user journeys, not only
isolated endpoints.

## Journey A --- Human and Agent

1.  User registers and configures profile/privacy.
2.  User creates an Agent and sees its Passport.
3.  User configures persona, skills, permissions, and budget.
4.  User uploads a permitted knowledge source.
5.  Ingestion finishes and source status is visible.
6.  Agent retrieves only authorized knowledge/memory.
7.  Agent executes a task through the AI Gateway and Runtime.
8.  User inspects trace, cost, sources, and result.
9.  User corrects/deletes memory or revokes a capability.
10. A subsequent run respects the updated state.

## Journey B --- Durable Workflow

1.  User creates a workflow using supported nodes.
2.  Workflow validation rejects invalid or unauthorized configuration.
3.  User runs the workflow.
4.  A safe checkpoint is persisted.
5.  Simulated/real infrastructure interruption occurs in test
    environment.
6.  Workflow resumes from the last valid checkpoint.
7.  Side effects are not duplicated.
8.  User can inspect the run timeline and error.

## Journey C --- Social Publishing

1.  Human or authorized Agent creates content.
2.  Media processing completes.
3.  Audience, moderation, and provenance rules are applied.
4.  Content appears in eligible Feed/Reels/Stories surfaces.
5.  Search/discovery indexes the content according to visibility.
6.  Block, delete, privacy change, or moderation action propagates to
    all surfaces.

## Journey D --- Universe and Live

1.  Authorized user creates a World/District/Booth using approved
    assets.
2.  Renderer loads manifest and scene data from official API.
3.  User navigates and interacts with a real POI.
4.  An event/stage is created in that spatial context.
5.  Participants join with correct roles and permissions.
6.  Human camera and AI virtual camera are separately permissioned.
7.  Realtime disconnect/reconnect preserves valid session state.
8.  Session closes and recording/replay follows consent and retention
    rules.

## Journey E --- Monetization

1.  Creator/tenant publishes an eligible listing.
2.  User views the pricing and entitlement terms.
3.  Purchase/subscription is initiated.
4.  Payment result is verified server-side.
5.  Ledger, credits, entitlements, and receipt are updated exactly once.
6.  Refund/cancel/chargeback changes state through a traceable reversal.
7.  Creator and platform reports reconcile to the same source ledger.

## Journey F --- Trust and Safety

1.  User reports content/Agent/booth/live event.
2.  Case is created with proper evidence access.
3.  Authorized reviewer makes a decision.
4.  Enforcement propagates to feed, search, messaging, world, catalog,
    and commerce as applicable.
5.  Affected party receives a privacy-safe notice.
6.  Appeal/reversal is traceable and does not erase original audit
    history.

------------------------------------------------------------------------

# 6. Suggested Execution Waves

Waves are planning groupings, not new phases. Phase numbers remain
stable for traceability.

  -----------------------------------------------------------------------
  Wave                    Included phases         Primary outcome
  ----------------------- ----------------------- -----------------------
  Wave A --- Control &    00--02                  Requirement contract,
  Platform                                        deployable baseline,
                                                  auth/data boundary

  Wave B --- Identity &   03--06                  Human identity, graph,
  Agent Core                                      Agent identity, skills

  Wave C --- AI           07--12                  Knowledge, memory, AI
  Intelligence Core                               routing, runtime,
                                                  workflow,
                                                  evaluation/rewards

  Wave D --- Social       13--20                  Content, feed, media,
  Content                                         stories, discovery,
                                                  messaging, communities,
                                                  notifications

  Wave E --- Spatial      21--24                  Spatial hierarchy, 3D
  Universe                                        pipeline, renderer,
                                                  characters/animation

  Wave F --- Live &       25--27                  Stage, realtime, events
  Events                                          

  Wave G --- Economy      28--31                  Marketplace, commerce,
                                                  billing, ads

  Wave H --- Trust &      32--36                  Safety, analytics,
  Operations                                      admin, developer
                                                  platform, observability

  Wave I --- Final        37                      Cross-domain QA,
  Validation                                      security regression,
                                                  release readiness
  -----------------------------------------------------------------------

### Cara menggunakan waves

-   Selesaikan dependency dan exit gate setiap phase; jangan hanya
    menandai seluruh wave selesai sekaligus.
-   Pekerjaan paralel boleh dilakukan jika kontrak API/data stabil dan
    tidak menimbulkan dua pemilik untuk satu domain.
-   Phase yang diblokir harus mencatat dependency dan evidence yang
    kurang, bukan membuat stub permanen.
-   Jika scope berubah, update requirement traceability dan ADR; jangan
    menyisipkan fitur diam-diam di phase QA.

------------------------------------------------------------------------

# 7. Cross-Cutting Architecture Contracts

Kontrak berikut berlaku di seluruh phase, bukan hanya satu domain.

## 7.1 API and backend boundary

-   UI memanggil API resmi.
-   Validasi, authorization, ownership, billing truth, moderation state,
    dan side effects diperiksa server-side.
-   API mempunyai schema, versioning policy, error contract, idempotency
    rules, pagination semantics, dan observability.
-   Tidak ada direct database access dari client untuk operasi yang
    seharusnya melewati backend/business policy.
-   Setiap endpoint sensitif memiliki negative authorization tests.

## 7.2 Database and migrations

-   Skema baru dibuat dari requirement, bukan menyalin asumsi
    implementasi lama.
-   Semua perubahan schema memakai migration yang dapat direview, diuji,
    dan dilacak.
-   Constraint/index dibuat berdasarkan integritas dan query patterns
    yang nyata.
-   Ownership, deletion, retention, uniqueness, idempotency, and audit
    semantics ditentukan sejak awal.
-   Migration tidak boleh menghapus data tanpa rencana eksplisit,
    backup, dan rollback/recovery strategy yang sesuai.

## 7.3 Agent authority

Setiap Agent action harus melewati evaluasi: 1. Siapa owner Agent? 2.
Apa capability yang aktif? 3. Apa permission scope yang diberikan? 4.
Siapa target/resource yang diakses? 5. Apakah audience/tenant/owner
boundary cocok? 6. Apakah action memiliki side effect? 7. Apakah
diperlukan approval/confirmation? 8. Apakah budget/quota masih cukup? 9.
Apakah policy/safety/moderation mengizinkan? 10. Bagaimana action
dicatat dan dihentikan/dibatalkan?

## 7.4 Memory and knowledge

-   Memory dan knowledge bukan satu tabel atau satu permission bucket
    yang tidak dibedakan.
-   Setiap item membawa owner, source, audience, retention, sensitivity,
    provenance, and lifecycle.
-   Retrieval filter dijalankan sebelum konten masuk ke prompt/context.
-   Publicly published knowledge hanya dapat diakses sesuai publikasi
    dan lisensinya; ia tidak boleh otomatis membuka seluruh memory
    owner.
-   Deletion/revocation harus merambat ke derived data, index, cache,
    and pending jobs.

## 7.5 Long-running work

-   Run memiliki ID stabil, state machine, checkpoint, event history,
    retry policy, and cancellation semantics.
-   Setiap side effect harus idempotent atau memiliki strategi
    deduplication/compensation.
-   Retry tidak boleh mengabaikan permission changes, budget changes,
    atau policy updates.
-   Client disconnect tidak berarti server-side work boleh kehilangan
    status tanpa kontrak eksplisit.

## 7.6 3D asset and spatial runtime

-   File berada di storage bukan berarti asset valid, aman, berlisensi,
    atau published.
-   Manifest, hash/checksum, size, asset version, compatibility,
    moderation status, and entitlement harus dapat diverifikasi.
-   Renderer harus memiliki performance budget, graceful fallback,
    cleanup lifecycle, dan telemetry.
-   Spatial hierarchy dan object IDs harus stabil agar event, ads,
    content, Agent, and commerce merujuk entitas yang sama.

## 7.7 Billing and credits

-   Ledger adalah sumber kebenaran saldo dan pergerakan nilai.
-   Payment callback tidak boleh dipercaya hanya karena datang dari
    client.
-   Webhook harus diverifikasi, idempotent, replay-protected, dan
    direkonsiliasi.
-   Credits, reward points, subscription entitlements, creator earnings,
    and cash settlement harus dibedakan secara semantik.
-   Semua koreksi menggunakan adjustment/reversal yang dapat diaudit,
    bukan mengubah history secara diam-diam.

## 7.8 Observability and evidence

-   Setiap request/run/job memiliki correlation identifier yang dapat
    ditelusuri.
-   Log tidak boleh menyimpan secret atau raw private content tanpa
    kebutuhan dan izin yang sah.
-   Evidence harus menyatakan environment, commit/build, waktu, test
    scope, hasil, dan batasan.
-   Screenshot hanya membuktikan tampilan; screenshot tidak membuktikan
    API, database, authorization, atau payment correctness.
-   Build hijau bukan bukti bahwa seluruh product journey sudah bekerja.

------------------------------------------------------------------------

# 8. Artefak Wajib per Phase

Setiap phase menyimpan artefak berikut, sesuai relevansi:

1.  `phase-plan.md` --- tujuan, scope, non-goals, dependencies, owner.
2.  `requirements-traceability.md` --- requirement ID ke implementasi
    dan test.
3.  `architecture-notes.md` atau ADR --- keputusan yang memengaruhi
    kontrak.
4.  `data-migrations/` --- migration dan test schema jika ada.
5.  `api-contracts/` --- OpenAPI/schema/error contract yang diperbarui.
6.  `security-review.md` --- trust boundary, permissions, abuse cases,
    test results.
7.  `test-plan.md` --- positive, negative, edge, regression, and
    recovery cases.
8.  `test-results/` --- output test yang dapat diulang.
9.  `ui-evidence/` --- screenshot/video untuk screen state yang relevan.
10. `api-evidence/` --- request/response yang sudah disanitasi.
11. `operations-runbook.md` --- deploy, diagnose, retry,
    rollback/recovery.
12. `phase-completion-report.md` --- status, evidence links/IDs, known
    limitations, sign-off.

Jangan membuat file kosong hanya untuk memenuhi nama artefak. Jika
artefak tidak relevan, tandai alasan pengecualiannya secara eksplisit.

------------------------------------------------------------------------

# 9. Aturan Penanganan Temuan

## Jika implementasi belum ada

Buat backlog pada phase yang benar dan tandai phase terkait `BLOCKED`
atau `IN_PROGRESS`. Jangan membuat UI palsu untuk memberi kesan selesai.

## Jika API ada tetapi UI belum terhubung

Phase belum complete. Implementasikan UI dan sambungkan ke API nyata,
termasuk empty/error/loading states.

## Jika UI ada tetapi API belum nyata

Phase belum complete. Jangan mengganti API dengan hardcoded response
untuk menutup gap.

## Jika schema/data tidak sesuai requirement

Buat migration/reconciliation plan dan test data integrity. Jangan
menambahkan tabel duplikat untuk menghindari perbaikan model domain.

## Jika test gagal

Simpan failure evidence, root-cause analysis, fix, dan regression test.
Jangan menonaktifkan test atau memperlebar assertion tanpa alasan yang
dapat direview.

## Jika security/privacy test gagal

Anggap sebagai blocker. Perbaiki boundary di server/data policy;
menyembunyikan tombol di UI bukan perbaikan authorization.

## Jika phase akhir menemukan fitur yang hilang

Kembalikan ke phase implementasi terkait. Phase 37 hanya menguji dan
memvalidasi, bukan mengimplementasikan fitur baru.

------------------------------------------------------------------------

# 10. Phase Status Board Template

Gunakan tabel berikut sebagai status board; jangan mengisi status
berdasarkan perkiraan.

  -----------------------------------------------------------------------------------------------------------------------------
  Phase    Status        Dependencies   API        DB evidence      UI evidence        Security   E2E/regression   Sign-off
                         met            evidence                                       tests                       
  -------- ------------- -------------- ---------- ---------------- ------------------ ---------- ---------------- ------------
  00--37   NOT_STARTED / Evidence       Evidence   Migration/test   Screenshot/video   Report ID  Report ID        Owner/date
           IN_PROGRESS / required       ID/link    ID               ID                                             
           BLOCKED /                                                                                               
           IN_REVIEW /                                                                                             
           COMPLETE                                                                                                

  -----------------------------------------------------------------------------------------------------------------------------

Untuk pelaporan terperinci, buat satu baris per phase, bukan hanya
rentang `00–37`.

------------------------------------------------------------------------

# 11. Rekomendasi Urutan Eksekusi Praktis

1.  Mulai dari Phase 00 dan 01 untuk menyelesaikan kontrak requirement
    dan platform baseline.
2.  Selesaikan Phase 02 sebelum membangun fitur yang membutuhkan
    identitas atau data privat.
3.  Selesaikan Phase 03--06 agar owner, social graph, Agent identity,
    dan capability boundary tersedia.
4.  Bangun Phase 07--12 sebagai satu rangkaian AI intelligence core;
    jangan mengaktifkan Agent publik sebelum memory/privacy, runtime,
    permissions, and evaluation layak.
5.  Bangun Phase 13--20 untuk mengaktifkan pengalaman sosial berbasis
    content dan komunikasi.
6.  Bangun Phase 21--24 untuk fondasi dan pengalaman spatial 3D.
7.  Bangun Phase 25--27 setelah stage, character contract, and realtime
    prerequisites siap.
8.  Bangun Phase 28--31 setelah identity, moderation, ledger,
    entitlement, and payment verification siap.
9.  Bangun Phase 32--36 sebagai kontrol lintas-domain dan operational
    readiness yang nyata---bukan hanya dashboard kosmetik.
10. Jalankan Phase 37 sekali seluruh phase wajib selesai dan release
    candidate stabil.

Urutan tersebut dapat diparalelkan pada pekerjaan yang tidak
berbenturan, tetapi tidak boleh mengubah dependency atau exit gate tanpa
ADR dan traceability update.

------------------------------------------------------------------------

# 12. Batas Scope dan Hal yang Tidak Boleh Diasumsikan

-   Jumlah domain bukan jumlah engine; beberapa domain berbagi engine.
-   "AI Agent bisa melakukan X" berarti ada capability contract,
    permission, runtime, UI, observability, dan test---bukan sekadar
    prompt.
-   "3D tersedia" berarti asset tervalidasi, manifest cocok, izin benar,
    renderer bekerja, dan performance budget dipenuhi.
-   "Realtime tersedia" berarti lifecycle, reconnect, permissions,
    monitoring, and fallback diuji---bukan sekadar tombol join.
-   "Marketplace tersedia" berarti listing, eligibility, permission,
    transaction/entitlement, moderation, and lifecycle benar.
-   "Monetisasi tersedia" berarti payment verification, ledger,
    reconciliation, refunds, entitlements, and reporting bekerja.
-   "Secure" tidak cukup dibuktikan oleh login; authorization, tenant
    isolation, IDOR, abuse, secret handling, and audit harus diuji.
-   "Production-ready" tidak sama dengan local build success.
-   Nama vendor, model, provider, dan layanan infrastruktur dipilih
    melalui ADR terpisah setelah requirements, cost, privacy,
    reliability, and deployment constraints dinilai. Phase plan ini
    tidak mengunci vendor tertentu.
-   Fitur atau domain tambahan di luar Master PRD harus masuk melalui
    change control; jangan menyisipkan scope baru tanpa memperbarui
    requirement map.

------------------------------------------------------------------------

# 13. Definition of Product Completion

Allpha dianggap siap dirilis hanya jika:

-   Semua requirement release-critical memiliki traceability ke
    implementasi dan test.
-   Setiap phase yang diperlukan berstatus `COMPLETE` dengan evidence
    yang dapat diverifikasi.
-   Critical user journeys lulus di mobile dan web.
-   Backend adalah sumber kebenaran dan seluruh business actions
    melewati policy yang tepat.
-   Data isolation, Agent authority, memory privacy, content visibility,
    and admin permissions terbukti lewat negative tests.
-   AI Gateway/Runtime memiliki cost controls, usage metering, failure
    handling, and evaluation.
-   Workflow yang panjang dapat checkpoint/resume dengan side effects
    yang aman.
-   Social/content surfaces konsisten terhadap privacy, moderation, and
    deletion.
-   Spatial/3D assets dapat diverifikasi dan renderer mempunyai
    fallback/performance evidence.
-   Live/voice/camera capabilities menghormati consent dan permission.
-   Billing/credits/commerce/ads dapat direkonsiliasi dan tidak
    bergantung pada klaim client.
-   Observability, alerts, incident response, backups, restore, and
    rollback telah diuji.
-   Tidak ada release-blocking security/privacy/data integrity issue
    yang belum diselesaikan.
-   Release report menyebutkan batasan yang diketahui secara jujur dan
    menyertakan sign-off.

------------------------------------------------------------------------

## Ringkasan

Roadmap ini terdiri dari **38 phase bernomor 00--37**. Phase 00--36
membangun kemampuan produk secara vertical slice, sedangkan **Phase 37
khusus untuk final cross-domain E2E, security regression, dan release
validation**. Setiap phase harus menyelesaikan backend/engine, database,
UI terhubung, integrasi, security/isolation, tests, dan evidence yang
relevan sebelum dinyatakan selesai.

Dokumen ini adalah baseline implementasi yang diturunkan dari Master PRD
v3.0.0. Jika ada konflik, requirement traceability dan keputusan produk
yang disahkan harus diperbarui secara eksplisit; jangan menyelesaikan
konflik dengan asumsi diam-diam.

---

# 14. Rekonsiliasi Kanonis dengan Master PRD v3.0.0

**Status rekonsiliasi:** struktur 38 phase (00–37) pada dokumen ini dipertahankan. Phase 21–24 adalah jalur inti Spatial/Theme/Renderer/Character. Phase 37 tetap final QA/release gate dan tidak boleh dipakai untuk menyelundupkan implementasi fitur. Master PRD v3.0.0 di `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md` tetap sumber requirement produk; dokumen ini mengatur urutan eksekusi dan exit gate. Jika nomor phase di dokumen lain berbeda, jangan menyatukan nomor dengan asumsi: catat crosswalk/ADR sebelum mengubah nomor atau dependency.

## 14.1 Phase crosswalk untuk GLB sampai UI/UX aplikasi

| Tahap kerja | Phase kanonis | Hasil yang harus nyata | Gate sebelum lanjut |
|---|---|---|---|
| Asset source/artifact inventory, provenance, dedup, license | 00, 22 | Inventory manifest per file; source URL/repo/commit/path, SHA-256, bytes, duplicate group, license evidence, attribution, review status | Aset tanpa bukti hak/provenance dikarantina; download sukses bukan approval |
| Theme taxonomy & asset-to-category mapping | 21, 22 | Pemetaan per asset ke 1 kategori utama dari 14 canonical keys; kategori sekunder hanya dengan alasan; Theme/Theme Version/World Template/Scene Schema links | Tidak membuat registry atau kategori duplikat; unresolved fit tetap `candidate` |
| GLB technical QA and optimization | 22 | Parse GLB 2.0, declared length, nodes/meshes/materials/textures, external dependencies, bounds/scale, transforms, animation/rig, texture/triangle budgets, compression/LOD variants, checksum | Invalid, malicious, oversized, broken texture, or unsupported rig → quarantine/reject |
| Official ingest and lifecycle | 22, 34 | Server-side upload/registration through the canonical lifecycle API; immutable asset ID/version; manifest, storage object key, checksum, size, license and review metadata | Never write directly to `theme_assets` as a lifecycle bypass; no partial promotion |
| Moderation, license and publication approval | 22, 32, 34 | Review decision with reviewer, timestamp, reason, license/attribution and safety/performance state; publish/rollback/takedown evidence | Only licensed/authorized, validated, approved versions may enter public manifest |
| Theme/World Builder and native asset library UX | 22, 23 | Browse/filter by theme/category/status; preview; loading/error/empty/denied states; placement/transform/replace/undo where supported; moderation state visible to authorized roles | UI calls official API; no client-only approval or invented asset state |
| World renderer & city scene composition | 21, 23 | Manifest-driven renderer loads approved assets by ID/version; combines World base, District A–D, landmark, portal, Booth, Agent, capsule and live stage roles through validated Scene Schema | Scene records/POI IDs are backend-authoritative; GLB nodes are presentation only |
| Native Android/iOS UX & performance | 01, 23, 24 | Touch orbit/pan/zoom, guided navigation, POI detail sheet, map/list fallback, loading progress, retry, cancel-on-exit, reduced motion/accessibility; real device evidence | Desktop/browser screenshot is not native-device QA; fallback must work when 3D cannot load |
| Character/animation integration | 24 | AgentCharacterTemplate and Human/Live assets mapped to rig/animation capabilities; preview and safe fallback | Never advertise animation or likeness capability unsupported by the asset contract |
| District/Booth/content/live integration | 23, 25, 26, 27, 29, 31 | POIs resolve to canonical District/Booth/Content/Agent/Live/Event/Ad/Commerce entities and enforce server permissions | Renderer must not grant ownership, entitlement, billing, publication, or moderation rights |
| End-to-end proof and release | 36, 37 | Authenticated API → authorized manifest/signed URL → GLB load → District navigation/POI interaction; negative access tests, device/perf QA, logs and build refs | No GREEN from CI or screenshots alone; all acceptance evidence attached |

### Wajib: jalur lifecycle GLB

`acquire → inventory → deduplicate → provenance/license review → validate → optimize → manifest → official lifecycle API/storage → review/moderation → publish approved version → authorized manifest/signed URL → renderer → native Android/iOS visual + interaction QA → telemetry → rollback/takedown test`.

Setiap langkah harus menghasilkan state persisten dan evidence. Storage presence, valid GLB header, green workflow, or a visible preview alone does not authorize publication.

## 14.2 Empat belas kategori Theme 3D Template — mapping contract

Gunakan exact keys berikut sebagai kategori kanonis. Setiap file inventaris memperoleh `asset_id`, filename, source, commit/path, SHA-256, byte size, primary category, optional secondary roles, Theme/Theme Version, intended scene role, license/provenance status, technical QA status, moderation status, publish status, and evidence reference.

| Key | Peran asset yang dipetakan | Penerapan di scene/UI |
|---|---|---|
| `universe` | Universe-scale backdrop/entry composition | Universe discovery/entry; tidak mengandung hak akses |
| `galaxy` | Galaxy cluster/overview visual | Galaxy selector/overview |
| `world` | World shell/ground/environment | Base scene dan world detail |
| `orbit` | Orbit rings, paths, navigation arcs | Navigation/orbit overlays; bukan sumber posisi otoritatif |
| `capsule` | Content/AI capsule shell | Content Capsule POI yang mengambil konten berizin melalui API |
| `district` | District block, streetscape, landmark, modular urban scene | City composition dan District navigation |
| `booth` | Booth/storefront shell | Booth/tenant POI; data tenant/commerce dari API |
| `content-feed` | Feed/content media surface, billboard/videotron frame | Konten yang sudah diterbitkan dan eligible |
| `agent-character` | AI character/avatar visual | Public/private character preview sesuai permission |
| `live-stage` | Podcast, talkshow, classroom, mentor, news, presentation stage | Live venue linked to real session/template |
| `human-live` | Human avatar/live participant/camera representation | UI participant identity; camera access tetap eksplisit |
| `sticker-social` | Sticker/reaction/social decorative objects | Dekorasi; tidak mengubah state interaksi sosial |
| `animation` | Rigged animation, clips, gestures, facial/viseme assets | Hanya capability yang dinyatakan dalam animation contract |
| `navigation-fx` | Portal, waypoint, pointer, spawn/teleport VFX | Wayfinding/transition cues; permission tetap server-side |

**Pemetaan awal 25-file pack yang terverifikasi lokal** (bukan 350 file terpisah): komponen berulang dalam pack adalah `WorldGround`, `District_A`, `District_B`, `District_C`, `District_D`, `WorldLandmark`, `PortalGateway`, `BoothTemplate`, `AgentCharacterTemplate`, `ContentAICapsule`, `LiveExperienceStage`. Gunakan mapping awal berikut untuk triage, lalu tetapkan nama file + SHA-256 dari manifest sebenarnya sebelum mendaftarkan asset:
- `WorldGround` → `world` (secondary `district` hanya jika satu file memang menyertakan modular district geometry).
- `District_A` / `District_B` / `District_C` / `District_D` → `district`.
- `WorldLandmark` → `district` (secondary `navigation-fx` hanya bila node/contract memang VFX/navigation).
- `PortalGateway` → `navigation-fx` (secondary `orbit` bila asset benar-benar orbit geometry).
- `BoothTemplate` → `booth`.
- `AgentCharacterTemplate` → `agent-character`; rigged animation tetap harus dibuktikan terpisah untuk kategori `animation`.
- `ContentAICapsule` → `capsule`; `content-feed` hanya jika ada media surface yang sesuai.
- `LiveExperienceStage` → `live-stage`.
- `universe`, `galaxy`, `orbit`, `human-live`, `sticker-social`, and `animation` remain **unmapped/needs candidate selection** unless a manifest entry and binary inspection prove a suitable asset. Do not force-fit an asset to fill a slot.

The 25 Themes × 14 categories = 350 **template slots**, not a claim of 350 unique approved GLBs. One GLB can serve multiple roles only when metadata/Scene Schema explicitly supports them and its license, size/performance, and runtime behavior pass every relevant gate.

## 14.3 Kombinasi 3D Districts Kota Allpha

Susun city scene dari komponen yang sudah lolos publish, bukan dari nama file semata:

1. **World base:** `WorldGround` (one canonical world-scale base, with world coordinate/unit contract).
2. **District A — Civic & Business Core:** central plaza, main navigation hub, civic/business landmarks and discovery entry.
3. **District B — Creator & Commerce:** tenant Booths, storefronts, marketplace entry points; product/order/tenant data resolved through official APIs.
4. **District C — Community & Culture:** community/event spaces, social capsules and cultural landmarks; only public/eligible content is loaded.
5. **District D — Innovation & Live:** AI Agent presence, classroom, podcast/talkshow/presentation/news stages and live experiences; session status and participant permissions come from backend.
6. **Shared POIs:** `WorldLandmark`, `PortalGateway`, `BoothTemplate`, `AgentCharacterTemplate`, `ContentAICapsule`, `LiveExperienceStage` linked to stable canonical domain IDs.
7. **Navigation contract:** District maps, walkable navigation, waypoints, spawn/exit and map/list fallback use the same persisted coordinates and POI IDs.
8. **Scene contract:** placement/transforms live in validated Scene Schema/World DSL. Never generate executable code from scene input; never treat GLB node names as business records.
9. **Runtime:** lazy-load District-specific assets, cancel in-flight loads on navigation away, clean GPU resources, support LOD/culling/device budgets, reduced motion and non-3D fallback.
10. **Acceptance:** open World → enter each authorized District → view/select a POI → open native detail sheet → resolve live API entity → test unauthorized/private POI denial → reload/reconnect → verify same persisted placement and state.

**Pack validation evidence known at specification time:** ZIP had 25 GLB files; local integrity checks found GLB 2.0 headers and manifest SHA/length matches, 24 unique hashes across 25 filenames (at least one duplicate geometry/content), combined size 361,736 bytes. These are lightweight stylized templates, not proof of a photorealistic/complete city. The ZIP did not establish third-party license rights. Therefore these files remain candidates until provenance/license review and official storage/lifecycle/runtime verification pass.

## 14.4 Acquisition artifact inventory — 927 unique GLB candidates

The previously reported acquisition audit found 933 candidate references, 927 downloaded unique GLBs, 6 duplicate-hash references, 0 missing files and 0 structural failures. These are **candidate inventory metrics only**. The audit did not establish publication rights or production readiness; last known license classification reported zero production-approved assets. The exact per-file artifact manifest must be committed beside the acquisition scripts and referenced here. For every row, compute primary category using filename/metadata hints only as a proposal; then confirm by inspecting actual geometry/material/texture/animation and scene context. Persist per-row status `unmapped`, `candidate`, `quarantined_license`, `quarantined_technical`, `approved_staged`, `published`, or `rejected`. Do not create a synthetic 927-row list or fabricate mappings if the actual manifest is not present.

## 14.5 Required artifacts and suggested repo locations

- `docs/PHASES/ALLPHA_UNIVERSE_IMPLEMENTATION_PHASE_MASTER_PLAN_v1.1.0.md` — this reconciled plan and status checklist.
- `docs/3d/ALLPHA_3D_ASSET_INVENTORY.csv` — generated from real acquisition manifest, one row per file/reference; never hand-invent.
- `docs/3d/ALLPHA_14_CATEGORY_THEME_MAPPING.csv` — one row per asset/category assignment with confidence, evidence, and review status.
- `docs/3d/ALLPHA_DISTRICT_CITY_SCENE_COMPOSITION.md` — composition contract and native UI/UX acceptance.
- `docs/3d/ALLPHA_GLB_PUBLISH_EVIDENCE.md` — upload/lifecycle API response, manifest, checksum, signed URL, render/performance/security evidence.
- `docs/PHASES/phase-status-board.csv` — one row for each phase 00–37; status must be evidence-backed.
- These files must not claim that artifacts exist until committed. If generated from repository artifact outputs, preserve a reproducible generator and source reference.

## 14.6 Required per-phase check-off and status governance

Do not mark phases complete merely because code exists or CI is green. For every phase 00–37, maintain a separate status row and checklist with requirement scope, dependency status, implementation commit, migration evidence, API evidence, UI evidence, security tests, E2E/regression report, runtime/device evidence where applicable, limitations, reviewer/sign-off and date. Use:
- `[ ]` acceptance/evidence incomplete or not verified;
- `[x]` only when the acceptance criterion is satisfied and linked to reproducible evidence;
- status `NOT_VERIFIED`, `IN_PROGRESS`, `BLOCKED`, `IN_REVIEW`, or `COMPLETE`.

Every phase begins unchecked unless current repository and live-system evidence proves it complete. A new agent must read the entire Master PRD, this complete Phase Plan, the current status board, related phase docs, relevant architecture/API/schema/migrations, and latest evidence before execution. After any implementation, the agent must update this exact phase document/status board in the same PR/commit, tick only individually proven items, link commit/test/API/UI/security/runtime evidence, record blockers honestly, and never tick dependent phases just because a prerequisite phase was completed. If the status board is stale or evidence is missing, set `NOT_VERIFIED` and investigate; do not infer completion.

## 14.7 Phase-by-phase check-off board (initial reconciliation)

This initial board deliberately leaves all phase acceptance boxes unchecked; no new implementation was performed by this documentation reconciliation. Update a row only after verifying live repository source, migrations, official APIs, UI journeys, security and acceptance evidence.

| Phase | Domain | Initial status | Verified implementation | API/data evidence | UI/E2E/security evidence | Complete |
|---|---|---|---|---|---|---|
| 00 | Product contract & governance | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 01 | Platform foundation | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 02 | Database/Auth/Authorization | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 03 | Human identity/privacy | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 04 | Social graph | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 05 | Agent identity/passport | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 06 | Agent Studio/skills | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 07 | Knowledge ingestion | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 08 | Memory/retrieval | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 09 | AI Gateway/Model Router | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 10 | Agent Runtime | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 11 | Workflow orchestration | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 12 | Challenge/evaluation | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 13 | Content creation/media | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 14 | Feed | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 15 | Reels/media consumption | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 16 | Stories/moments | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 17 | Search/discovery | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 18 | Messaging | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 19 | Communities/collaboration | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 20 | Notifications | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 21 | Spatial hierarchy/navigation | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 22 | Theme/GLB asset pipeline | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 23 | World renderer/Districts/Booths | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 24 | Avatar/AI character/animation | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 25 | Live experience/stage | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 26 | Realtime/voice/streaming | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 27 | Events/scheduling | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 28 | Agent marketplace | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 29 | Commerce/creator economy | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 30 | Subscription/credits/billing | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 31 | Advertising/spatial ads | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 32 | Trust/safety/moderation | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 33 | Analytics/insights | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 34 | Super Admin | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 35 | Developer platform/API | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 36 | Observability/AI evaluation | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |
| 37 | Final E2E/release gate | NOT_VERIFIED | [ ] | [ ] | [ ] | [ ] |

---

## 14.8 Current reconciliation limitation and next executable step

Repository inspection for this documentation update confirms the Master PRD and AGENTS.md are present. The previous asset-acquisition evidence is summarized above, but the complete 927-row artifact manifest has not yet been cross-checked in this commit against per-file GLB geometry and rights. Accordingly this update **does not** claim all 927 files are mapped, uploaded to production Storage, published, or visible in native UI. Next executable task is to locate/commit the real artifact manifest, generate a reproducible 927-row mapping draft, review candidate assignments against all 14 categories, and run the official publish-to-render acceptance path without bypassing lifecycle governance.


## Execution checkpoint — 2026-10-13

- ADR-0001: accepted by Product Owner directive; crosswalk details remain a follow-up review.
- ENG-P00/Phase 00: governance documents exist, but independent repository/dependency/app test baseline evidence is still open. Do not mark ENG-P00 complete.
- ENG-P01: authorized and started on `feat/eng-p01-platform-foundation` to establish the missing deployable source baseline rather than wait for a separate app repository baseline that has not been confirmed.
- Current implementation will start with a minimal web/API thin slice and reproducible tests. Native mobile framework selection remains subject to ADR-0002; do not invent a final mobile framework decision in this scaffold.


## Execution mode update — Product Owner directive (2026-10-13)

- **Canonical implementation branch: `main` only.** Routine work must be committed directly to `main`; do not create new branches or require PR/approval workflow for implementation.
- **Keep CI simple:** run relevant build/test smoke checks; do not add multiple redundant audit/security/approval jobs as prerequisites to normal implementation. Fix actionable failures directly on `main`.
- **Monorepo topology:** maintain three separable product areas: `apps/client` (native Android/iOS plus web client where appropriate), `apps/super-admin`, and `apps/backend` (FastAPI API/domain services). Existing `apps/web` and `apps/api` can be migrated into these boundaries; avoid duplicate app implementations. Shared contracts/types live in a shared package and all privileged mutations flow through backend APIs.
- **GLB-to-UI path:** make developer-owned assets available to the catalog/manifest and renderer through a direct, simple API/Storage path. Do not require a manual multi-step approval chain merely to preview/render an asset in developer UI. Use only lightweight automatic format/readability checks and visible errors. Public exposure and uncertain licensing must remain explicit; a preview does not silently declare rights cleared.
- Security hardening and comprehensive validation can be expanded after the product and integrations are functioning. Basic secret isolation, real data, and correct ownership/API boundaries remain in place from the start.
- ENG-P01 foundation was merged into `main` by commit `0d46d97c1df23aca0c96cf88a159e60422270315`. Its CI was not green at merge time; treat the thin slice as present but do not claim the workflow passed. Fix the smallest actionable CI issue directly on `main` as implementation continues.
- Next implementation target: ENG-P02 — Supabase database connectivity, authentication/session wiring, and tenant/resource ownership boundaries, then ENG-P03 identity/profile. In parallel, build the client/admin/backend monorepo shape and the straightforward GLB catalog-to-renderer path.


## ENG-P01 execution update — direct-main implementation (2026-10-13)

- Implementation policy is direct commits to `main`; no new branch was created for this work.
- Current foundation files: `apps/api` FastAPI thin slice; `apps/web` Next.js thin slice; `apps/client/README.md` and `apps/super-admin/README.md` establish extractable boundaries; root `README.md`, `.env.example`, `docker-compose.yml`, `apps/web/Dockerfile`, and Next standalone output document/provide local container deployment.
- Smoke CI workflow is lightweight: API pytest and web production build only. A previous main run passed both jobs: [run 38350451270](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38350451270). Newer runs after container/deployment changes must be checked separately; do not use the earlier green run as proof that later commits built.
- ENG-P01 status remains `in_progress`: npm/pip transitive lockfiles are not committed yet, actual staging/production deployment has not been performed, and latest CI for the deployment changes is pending. Direct dependency versions are pinned for web; full dependency reproducibility is still outstanding.
- Supabase project `dvdziauyvuhcnqhrrvww` (AllphaAiAplikasi-db) is reachable and ACTIVE_HEALTHY, but the inspected `public` schema currently shows no product tables; this foundation does not yet connect API/auth to Supabase. That is ENG-P02 work, not a reason to block this thin slice.
- Next: finish lockfile strategy and confirm latest CI; then ENG-P02 connects canonical Supabase, session/auth and ownership. Build asset catalog → GLB manifest → renderer as an early vertical slice after API/data foundation.


## ENG-P02 execution update — canonical Supabase (2026-10-13)

- Current implementation details and acceptance gates: [ENG-P02 Database & Authorization](./ENG_P02_DATABASE_AUTHORIZATION.md).
- Canonical Supabase project: AllphaAiAplikasi-db, ref dvdziauyvuhcnqhrrvww. Live inspection found existing profiles, organizations, and organization_memberships tables with RLS, contrary to the earlier ENG-P01 note that public was empty. The earlier note is superseded by the actual live schema inspection recorded in the ENG-P02 document.
- Additive migrations applied to the canonical project: identity/tenant baseline was already recorded at 20261013052302; authorization/audit at 20261013052409; security-definer grants at 20261013052557; private-schema helpers at 20261013052733; organization-creation audit at 20261013052744. Repository migration files now use the corresponding version names. The first baseline SQL was reconstructed from live schema because its original source was absent from the repository; exact historical byte-for-byte parity is not claimed.
- API now validates Supabase Auth bearer tokens server-side and passes the caller JWT to PostgREST so RLS remains authoritative. Added /v1/me, PATCH /v1/me/profile, GET/POST /v1/organizations, and tenant membership listing. No service-role key is used in these routes.
- Security Advisor returned no findings after moving authorization helper functions into the non-exposed private schema and restricting trigger function execution.
- ENG-P02 remains IN_PROGRESS until CI is green for the latest commit, real Supabase Auth/profile/org flows and cross-tenant authorization tests pass, and deployment secrets/configuration are exercised in the target environment. Do not mark integration_verified or acceptance_passed based on schema and unit smoke tests alone.
- Next dependency after ENG-P02 acceptance: ENG-P03 Identity/Profile completion, followed by early GLB catalog → authorized manifest/API → renderer vertical slice. Keep all routine commits directly on main.
