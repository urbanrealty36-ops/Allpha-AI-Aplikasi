import assert from "node:assert/strict";
import { findInvalidMeshoptFallbackBuffers } from "../../../tools/3d-assets/meshopt-fallback-compat.mjs";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { existsSync, readFileSync } from "node:fs";

const page = readFileSync(new URL("../app/agents/[agentId]/studio/page.tsx", import.meta.url), "utf8");
const agents = readFileSync(new URL("../app/agents/page.tsx", import.meta.url), "utf8");

assert.ok(page.includes("/v1/agents/${encodeURIComponent(agentId)}/knowledge/retrieve"));
assert.ok(page.includes('Authorization: "Bearer " + session.access_token'));
assert.ok(page.includes('method: "POST"'));
assert.ok(page.includes("setRetrievalLoading(true)"));
assert.ok(page.includes("API sedang mencari knowledge yang diizinkan"));
assert.ok(page.includes('role="alert"'));
assert.ok(page.includes("Coba lagi"));
assert.ok(page.includes("API mengembalikan 0 hasil untuk query ini"));
assert.ok(page.includes("Trace ID:"));
for (const field of ["source_id", "source_version", "chunk_id", "content_sha256", "source_location", "sensitivity", "retrieval_method", "score"]) {
  assert.ok(page.includes(field), `missing retrieval provenance field: ${field}`);
}
assert.ok(page.includes("retrievalRequestSequence.current"));
assert.ok(page.includes("}, [agentId]);"));
assert.ok(page.includes("requestSequence !== retrievalRequestSequence.current"));
assert.ok(page.includes("preview konteks retrieval, bukan respons generatif Agent"));
assert.ok(page.includes('href="/skill-challenges"'), "Agent Studio must link to Skill Challenge");
assert.doesNotMatch(page, /mockRetrievalResults|fakeKnowledgeResults|fixtureRetrieval/);


for (const contract of [
  "/v1/agent-runtime/tasks", "createRuntimeTask", "runtimeTaskAction",
  "idempotency_key", "Pulihkan status", "Batalkan",
  "Jalankan", "Skill terpublikasi", "runtimeTasks"
]) assert.ok(agents.includes(contract), `missing Web runtime lifecycle contract: ${contract}`);
assert.ok(agents.includes('/v1/agent-runtime/sessions/'));
assert.ok(agents.includes('task.state !== "created"'));
assert.ok(agents.includes('execution outcome') || agents.includes("hasilnya tidak diketahui"));


const workflows = readFileSync(new URL("../app/workflows/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/workflows/definitions", "/v1/workflows/runs", "Authorization: \"Bearer \" + session.access_token",
  "createDefinition", "createRun", "inspectRun", "cancelRun", "selectedRun.steps",
  "selectedRun.events", "JSON.parse(definitionText)", "JSON.parse(inputText)",
  "worker yang dikonfigurasi secara terpisah", "role=\"alert\"", "Coba lagi"
]) assert.ok(workflows.includes(contract), `missing Workflow Engine Web contract: ${contract}`);
assert.doesNotMatch(workflows, /SUPABASE_SERVICE_ROLE_KEY|service_role/i);
assert.ok(workflows.includes("setSupabase(getBrowserSupabase())") && workflows.includes("after hydration"), "Workflow Supabase client must initialize after hydration to avoid duplicate server/client fallback UI");
assert.ok(workflows.includes('if (!supabase) return <main className="identity-shell">') && workflows.includes("  </main>;\n}"), "Workflow fallback and main page must be separate, well-formed return branches");
const globalStyles = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
assert.ok(globalStyles.includes(".config-card p{overflow-wrap:anywhere}"), "Workflow configuration keys must wrap at narrow mobile widths");

const challenges = readFileSync(new URL("../app/skill-challenges/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/skill-challenges/catalog?agent_id=", "/v1/skill-challenges/runs", "idempotency_key",
  "nonce", "evidence_digest", "evaluation_result", "Expected output tidak dikirim ke browser.",
  "Jalankan Skill & evaluasi", "/execute", "/comparison", "/release-decision", "Catat keputusan release", "Model Router", "Authorization: \"Bearer \" + session.access_token"
]) assert.ok(challenges.includes(contract), `missing Skill Challenge Web contract: ${contract}`);
assert.doesNotMatch(challenges, /SUPABASE_SERVICE_ROLE_KEY|service_role/i);

for (const contract of [
  "/v1/skill-catalog?limit=100&offset=", "allpha_skill_key", "allpha_skill_catalog_version",
  "character_profile", "Pilih satu Skill", "catalogSkills", "asset GLB belum otomatis tersedia"
]) assert.ok(agents.includes(contract), `missing Agent Identity Skill catalog contract: ${contract}`);
const superAdminPath = new URL("../../super-admin/app/page.tsx", import.meta.url);
if (existsSync(superAdminPath)) {
const superAdmin = readFileSync(superAdminPath, "utf8");
  for (const contract of [
    "/v1/admin/official-bots", "/v1/admin/official-bots/provision", "Siapkan kandidat", "Agency Agents · metadata-only", "catalog_source",
    "officialBotAction", "Aktifkan", "Stop", "Isolasi", "asset_validation_status"
  ]) assert.ok(superAdmin.includes(contract), `missing Super Admin Official Bot control contract: ${contract}`);
  assert.doesNotMatch(superAdmin, /SUPABASE_SERVICE_ROLE_KEY|service_role/i);
}

// ENG-P13 Creator Studio + moderation contracts: authenticated API only; no mocked business records.
const contentStudio = readFileSync(new URL("../app/content-studio/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/content/mine", "/v1/content", "/media", "/preview", "/publish", "/retry",
  "Authorization", "session.access_token", "FormData", "preview_url", "visibility", "content_type",
  "Konten dikirim untuk ditinjau."
]) assert.ok(contentStudio.includes(contract), `missing ENG-P13 Web content contract: ${contract}`);
assert.doesNotMatch(contentStudio, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockContentItems|fakeFeed/);

const moderationPath = new URL("../../super-admin/app/content-moderation/page.tsx", import.meta.url);
if (existsSync(moderationPath)) {
const moderation = readFileSync(moderationPath, "utf8");
  for (const contract of [
    "/v1/content/admin/review-queue", "/v1/content/admin/", "expected_version",
    "Authorization", "access_token", "preview_url", "approve", "reject", "reason"
  ]) assert.ok(moderation.includes(contract), `missing ENG-P13 moderation contract: ${contract}`);
  assert.doesNotMatch(moderation, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockModerationQueue/);
}

const nativeContentPath = new URL("../../client/App.tsx", import.meta.url);
const nativeContent = existsSync(nativeContentPath) ? readFileSync(nativeContentPath, "utf8") : "";
if (existsSync(nativeContentPath)) {
  for (const contract of [
    "/v1/content/mine", "/v1/content", "/media", "/preview", "/publish", "/retry",
    "Authorization", "session.access_token", "DocumentPicker", "FormData",
    "Draft konten tersimpan melalui FastAPI", "Konten dikirim untuk moderasi"
  ]) assert.ok(nativeContent.includes(contract), `missing ENG-P13 Native content contract: ${contract}`);
  assert.doesNotMatch(nativeContent, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockContentItems|fakeFeed/);
}

const feedPage = readFileSync(new URL("../app/feed/page.tsx", import.meta.url), "utf8");
const feedPostCard = readFileSync(new URL("../components/feed/FeedPostCard.tsx", import.meta.url), "utf8");
const feedContract = feedPage + "\\n" + feedPostCard;
for (const contract of [
  "/v1/feed?", "/v1/feed/preferences", "/v1/feed/item/", "/reaction", "/save", "/comments", "/report", "/share",
  "personalization_enabled", "ranking_mode", "next_cursor", "Laporkan", "Bagikan", "reportReasons", "misinformation", "navigator.clipboard", "content"
]) assert.ok(feedContract.includes(contract), `missing ENG-P14 Web feed contract: ${contract}`);
assert.doesNotMatch(feedPage + feedPostCard, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockFeedItems|fakeFeed/);

const reportsPagePath = new URL("../../super-admin/app/content-reports/page.tsx", import.meta.url);
const reportsPage = existsSync(reportsPagePath) ? readFileSync(reportsPagePath, "utf8") : "";
if (existsSync(reportsPagePath)) {
  for (const contract of [
    "/v1/admin/content-reports", "/v1/admin/content-reports/", "platform:content.moderate",
    "dismiss", "hide_content", "Alasan keputusan", "Authorization", "preview_url", "media?.map"
  ]) assert.ok(reportsPage.includes(contract), `missing ENG-P14 Super Admin reports contract: ${contract}`);
  assert.doesNotMatch(reportsPage, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockReports/);
}

const reelsPage = readFileSync(new URL("../app/reels/page.tsx", import.meta.url), "utf8");
const reelsView = readFileSync(new URL("../components/reference-ui/ReelsView.tsx", import.meta.url), "utf8");
const reelsContract = reelsPage + "\\n" + reelsView;
for (const contract of [
  "/v1/reels?", "controls", "playsInline", "<audio", "preview_url", "toggleLike", "onShare={reel => void share(reel)}",
  "Tonton Reels publik. Masuk untuk menyukai, berkomentar, dan mengikuti kreator.", "onError", "Perbarui tautan media dan coba lagi", "mediaErrors"
]) assert.ok(reelsContract.includes(contract), `missing ENG-P15 Web Reels contract: ${contract}`);
assert.doesNotMatch(reelsPage, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockReels|fakeReels/);
assert.ok(contentStudio.includes("audio/mpeg") && contentStudio.includes("<audio"), "Creator Studio must upload and preview audio");
const moderationPagePath = new URL("../../super-admin/app/content-moderation/page.tsx", import.meta.url);
const moderationPage = existsSync(moderationPagePath) ? readFileSync(moderationPagePath, "utf8") : "";
if (existsSync(moderationPagePath)) assert.ok(moderationPage.includes("<audio"), "Super Admin moderation must preview audio");
if (existsSync(reportsPagePath)) assert.ok(reportsPage.includes("<audio"), "Super Admin report review must preview audio");

console.log("ENG-P08 retrieval, ENG-P10 task lifecycle, ENG-P11 workflow, ENG-P12 Skill Challenge, ENG-P13 content/moderation, ENG-P14 feed/reports, ENG-P15 Reels/audio, Agent Skill catalog, and Official Bot control smoke assertions passed.");

const meshoptHelper = readFileSync(new URL("../lib/spatial/configureAllphaGLTFLoader.ts", import.meta.url), "utf8");
assert.ok(meshoptHelper.includes("MeshoptDecoder"), "Web GLTF loader must import MeshoptDecoder");
assert.ok(meshoptHelper.includes("loader.setMeshoptDecoder(MeshoptDecoder)"), "Web GLTF loader must register MeshoptDecoder");
await MeshoptDecoder.ready;
assert.equal(typeof MeshoptDecoder.decodeGltfBuffer, "function", "Meshopt decoder must initialize before GLB parsing");
for (const [file, loadCall] of [
  ["../components/spatial/CanonicalGlbPreview.tsx", "useLoader(GLTFLoader, url, configureAllphaGLTFLoader)"],
  ["../components/spatial/CanonicalWorldRenderer.tsx", "useLoader(GLTFLoader, object.asset_url, configureAllphaGLTFLoader)"]
]) {
  const source = readFileSync(new URL(file, import.meta.url), "utf8");
  assert.ok(source.includes("configureAllphaGLTFLoader"), `missing Meshopt loader configuration in ${file}`);
  assert.ok(source.includes(loadCall), `GLTFLoader call is not configured for Meshopt in ${file}`);
}



const validMeshoptFallback = {
  extensionsRequired: ["EXT_meshopt_compression"],
  buffers: [
    { byteLength: 8 },
    { byteLength: 16, extensions: { EXT_meshopt_compression: { fallback: true } } }
  ],
  bufferViews: [{
    buffer: 1,
    byteLength: 16,
    extensions: { EXT_meshopt_compression: {
      buffer: 0, byteOffset: 0, byteLength: 8, byteStride: 4, count: 4, mode: "ATTRIBUTES"
    } }
  }]
};
assert.deepEqual(findInvalidMeshoptFallbackBuffers(validMeshoptFallback), [],
  "spec-conformant URI-less Meshopt fallback buffer must not be misclassified as malformed");
const invalidMeshoptFallback = structuredClone(validMeshoptFallback);
delete invalidMeshoptFallback.buffers[1].extensions.EXT_meshopt_compression.fallback;
assert.deepEqual(findInvalidMeshoptFallbackBuffers(invalidMeshoptFallback), [
  { index: 1, reasons: ["fallback_flag_missing"] }
], "URI-less nonzero buffer without fallback marker must be rejected");


const publishedThemeRoute = readFileSync(new URL("../app/theme/[themeKey]/page.tsx", import.meta.url), "utf8");
const worldRenderer = readFileSync(new URL("../components/spatial/CanonicalWorldRenderer.tsx", import.meta.url), "utf8");
const glbPreview = readFileSync(new URL("../components/spatial/CanonicalGlbPreview.tsx", import.meta.url), "utf8");
assert.ok(publishedThemeRoute.includes("CanonicalWorldRenderer"), "public Theme route must use the canonical renderer");
assert.ok(worldRenderer.includes("/v1/spatial/themes/") && worldRenderer.includes("/manifest"), "Web renderer must resolve the canonical published Theme manifest");
assert.ok(worldRenderer.includes("publication_status") && worldRenderer.includes("fallback_mode"), "Web renderer must enforce publication status and renderer fallback contract");
assert.ok(worldRenderer.includes("validateManifest") && worldRenderer.includes("themeKey"), "Web renderer must validate canonical manifest input");
assert.ok(glbPreview.includes("ALLPHA_ASSET_CATEGORIES") && glbPreview.includes("navigation-fx"), "Web GLB preview must expose the canonical 14-category taxonomy");
assert.ok(worldRenderer.includes("configureAllphaGLTFLoader"), "Web scene renderer must register the canonical GLTF loader");
assert.ok(worldRenderer.includes("onSelect={setSelectedEntityId}"), "Web renderer must wire scene object selection");
assert.ok(worldRenderer.includes("aria-label=\"Spatial interactions\""), "Web renderer must expose accessible spatial interaction details");
assert.ok(worldRenderer.includes("aria-pressed={object.entity_id === selectedEntityId}"), "Web object list must expose selection state");
assert.ok(worldRenderer.includes('m.coordinate_system !== "right-handed-y-up"'), "Web renderer must validate scene coordinate system");
assert.ok(worldRenderer.includes("Number.isSafeInteger(m.scene_version)"), "Web renderer must validate scene version");
assert.ok(worldRenderer.includes("!object.asset_id.trim()"), "Web renderer must reject missing asset identity");
assert.ok(worldRenderer.includes("object.asset_version < 1"), "Web renderer must reject invalid asset versions");
assert.ok(worldRenderer.includes("useLoader.clear(GLTFLoader, object.asset_url)"), "Web renderer retry must clear cached GLTFLoader failures");
assert.ok(glbPreview.includes("useLoader.clear(GLTFLoader, asset.asset_url)"), "Web GLB preview retry must clear cached GLTFLoader failures");
console.log("ENG-P22 Theme manifest and ENG-P23 Web renderer source smoke tests passed.");

const spatialThemeCatalog = readFileSync(new URL("../app/spatial/themes/page.tsx", import.meta.url), "utf8");
assert.ok(spatialThemeCatalog.includes("/v1/spatial/themes?limit=100&offset=0"), "Web Theme catalog must use canonical published-theme API");
assert.ok(spatialThemeCatalog.includes("CanonicalWorldRenderer themeKey={selected.theme_key}"), "Web Theme catalog must invoke canonical renderer");
assert.ok(spatialThemeCatalog.includes("Belum ada Theme publik"), "Web Theme catalog must provide a truthful empty state");
assert.ok(spatialThemeCatalog.includes("AbortController"), "Web Theme catalog must cancel stale requests on unmount");
assert.ok(spatialThemeCatalog.includes("Coba lagi"), "Web Theme catalog must provide retry on API failure");


// ENG-P13 / reference parity regression: Web Feed, Create, Stories and Reels
// are canonical-API-backed and must remain reachable from the Feed shell.
const webCreate = readFileSync(new URL("../app/create/page.tsx", import.meta.url), "utf8");
for (const contract of [
  '"/v1/content"', '"/v1/content/"', '"/media"', '"/publish"',
  "session.access_token", "FormData", "visibility", "content_type", "allowedMedia", "maxBytes", "file.size",
  "Konten belum", 'role="alert"', "moderation === \"approved\""
]) assert.ok(webCreate.includes(contract), "missing Web Create lifecycle contract: " + contract);
assert.doesNotMatch(webCreate, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockContentItems|fakeFeed/);

assert.doesNotMatch(webCreate, /aria-label="Navigasi utama"/, "Create must use shared global navigation without a duplicate local nav");
const webStoriesShell = readFileSync(new URL("../app/stories/page.tsx", import.meta.url), "utf8");
assert.doesNotMatch(webStoriesShell, /mb-6 flex items-center justify-between gap-3/, "Stories must use shared global navigation without duplicate route links");
const webReelsShell = readFileSync(new URL("../app/reels/page.tsx", import.meta.url), "utf8");
assert.doesNotMatch(webReelsShell, /href="\/feed"[^>]*>← Feed/, "Reels must not render duplicate page-local route navigation");


const webFeed = readFileSync(new URL("../app/feed/page.tsx", import.meta.url), "utf8");
const webFeedView = readFileSync(new URL("../components/reference-ui/FeedView.tsx", import.meta.url), "utf8");
const webFeedContract = webFeed + "\\n" + webFeedView;
for (const contract of ["/v1/feed", "/v1/feed/preferences", "session.access_token", 'role="alert"']) {
  assert.ok(webFeedContract.includes(contract), "missing Web Feed API/error contract: " + contract);
}
assert.doesNotMatch(webFeed, /mockFeedItems|fakeFeed/);

const webStories = readFileSync(new URL("../app/stories/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/stories", "/v1/content/", "/media", "/publish", "session.access_token", "FormData"]) {
  assert.ok(webStories.includes(contract), "missing Web Stories lifecycle contract: " + contract);
}
assert.doesNotMatch(webStories, /mockStories|fakeStoryItems/);

const webReels = readFileSync(new URL("../app/reels/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/reels", "/v1/feed/", "/reaction", "/share", "session.access_token"]) {
  assert.ok(webReels.includes(contract), "missing Web Reels API contract: " + contract);
}
assert.doesNotMatch(webReels, /mockReels|fakeReelItems/);

// The source reference intentionally switches only the bottom-navigation palette on Reels.
const referenceBottomNav = readFileSync(new URL("../components/reference-ui/BottomNav.tsx", import.meta.url), "utf8");
assert.ok(referenceBottomNav.includes("const isReels = activeTab === 'REELS'"), "bottom navigation must detect the active Reels route");
assert.ok(referenceBottomNav.includes("bg-black/90 backdrop-blur-lg border-t-2 border-slate-800"), "Reels must retain the source-reference dark bottom navigation");
assert.ok(referenceBottomNav.includes("bg-white border-t-2 border-slate-900"), "non-Reels routes must retain the source-reference light bottom navigation");
assert.ok(referenceBottomNav.includes("text-[#0284C7]"), "active navigation color must match the current route palette");

// Shared reference navigation owns route links; page-local duplicate navs are intentionally absent.
const referenceNavigation = readFileSync(new URL("../components/reference-ui/ReferenceNavigation.tsx", import.meta.url), "utf8");
const referenceFeedView = readFileSync(new URL("../components/reference-ui/FeedView.tsx", import.meta.url), "utf8");
for (const route of ['FEED: "/feed"', 'CREATE: "/create"', 'MESSAGES: "/messages"', 'REELS: "/reels"', 'WORLD3D: "/spatial/navigation"', 'LIVESTAGE: "/live"']) {
  assert.ok(referenceNavigation.includes(route), "global reference navigation missing route mapping: " + route);
}
for (const route of ["onOpenReels", "onOpenWorld3D", "onOpenLiveStage", "onOpenCreateModal"]) {
  assert.ok(referenceFeedView.includes(route), "reference Feed view missing navigation callback: " + route);
}
assert.ok(referenceNavigation.includes('onSearch={(query: string) => navigate("/search?q=" + encodeURIComponent(query))}'));

const webSearch = readFileSync(new URL("../app/search/page.tsx", import.meta.url), "utf8");
assert.ok(webSearch.includes("useSearchParams"), "Search must react to global navbar query updates");
assert.ok(webSearch.includes("lastUrlQuery.current === urlQuery"), "Search must avoid duplicate submissions for the same URL query");
assert.ok(webSearch.includes("<Suspense"), "Search useSearchParams must be guarded by Suspense for production build");
assert.ok(webSearch.includes('fetch(apiBase + "/v1/search?q="'), "Search must use the canonical authenticated Search API");
for (const contract of [
  "lastSessionUserId", "sessionEpoch.current += 1", "searchRequestSequence.current",
  "trendsRequestSequence.current", "recommendationsRequestSequence.current", "creatorsRequestSequence.current",
  "socialGraphRequestSequence.current", "/v1/me/social-graph", "/v1/me/social-edges",
  "pendingFollowAccountIds", "follow_request_created", "lastUrlQuery.current = null",
  "if (sequence !== searchRequestSequence.current) return",
  "if (sequence === trendsRequestSequence.current)", "if (sequence === recommendationsRequestSequence.current)",
  "if (sequence === creatorsRequestSequence.current)"
]) assert.ok(webSearch.includes(contract), "Search must isolate sessions and use canonical Social Graph contracts: " + contract);
const exploreView = readFileSync(new URL("../components/reference-ui/ExploreView.tsx", import.meta.url), "utf8");
assert.ok(exploreView.includes("pendingFollowAccountIds") && exploreView.includes("<span>Menunggu</span>") && exploreView.includes("Batalkan permintaan mengikuti"), "Explore must distinguish active follows from cancellable private-profile requests");
assert.ok(webSearch.includes("/v1/social/discover-users") && webSearch.includes("discoveredUsers") && webSearch.includes("discoverable"), "Explore must connect username discovery to the canonical saved-preference API");
assert.ok(exploreView.includes("discoveryError") && exploreView.includes("relationshipError"), "Explore must expose explicit discovery and relationship error states");
const socialFeedApiPath = new URL("../../api/src/allpha_api/feed_api.py", import.meta.url);
if (existsSync(socialFeedApiPath)) {
  const socialFeedApi = readFileSync(socialFeedApiPath, "utf8");
  for (const contract of [
    '"/v1/social/discover-users"', "discoverable_by_username", '"account_status": "eq.active"',
    "owner_profile.get(\"account_status\", \"active\")", '"/v1/social/follow/{target_user_id}"'
  ]) assert.ok(socialFeedApi.includes(contract), "Social Graph API must enforce discovery and active-profile privacy: " + contract);
}
assert.doesNotMatch(webSearch, /SOCIAL_ACCOUNTS_SAMPLE|INITIAL_POSTS|mockSearchResults|fakeSearch/);

const webMessages = readFileSync(new URL("../app/messages/page.tsx", import.meta.url), "utf8");
const webMessagesView = readFileSync(new URL("../components/reference-ui/MessagesView.tsx", import.meta.url), "utf8");
const webMessagesContract = webMessages + "\\n" + webMessagesView;
for (const contract of [
  "/v1/messages/conversations", "client_message_id", "postgres_changes",
  "const [search, setSearch]", "const [activeTab, setActiveTab]", "conversations.filter",
  'aria-label="Cari percakapan"', 'aria-label="Filter percakapan"', "aria-pressed={activeTab === tab.id}"
]) assert.ok(webMessagesContract.includes(contract), "missing API-backed Messages adapter contract: " + contract);
assert.ok(webMessages.includes("MessagesView"), "Messages route must mount the copied source inbox component");
assert.doesNotMatch(webMessages, /conversations = \[/);

// Native parity must expose the same canonical content/story/feed capabilities;
// source assertions do not substitute for Expo typecheck or device acceptance.
if (existsSync(nativeContentPath)) {
  for (const contract of [
    "/v1/content", "/v1/stories", "/v1/feed", "/v1/reels",
    "session.access_token", "DocumentPicker", "FormData"
  ]) assert.ok(nativeContent.includes(contract), `missing Native social/content parity contract: ${contract}`);
}


// Reference UI parity refinements must retain canonical API state and recoverable UI states.
const feedCard = readFileSync(new URL("../components/feed/FeedPostCard.tsx", import.meta.url), "utf8");
const createPage = readFileSync(new URL("../app/create/page.tsx", import.meta.url), "utf8");
const storiesPage = readFileSync(new URL("../app/stories/page.tsx", import.meta.url), "utf8");
const reelsPageParity = readFileSync(new URL("../app/reels/page.tsx", import.meta.url), "utf8");
const referenceNavbar = readFileSync(new URL("../components/reference-ui/Navbar.tsx", import.meta.url), "utf8");
const nativeApp = nativeContent;
assert.ok(feedCard.includes("ownerHandle") && feedCard.includes("@{ownerHandle}"), "Feed card must show the creator handle hierarchy from canonical owner identity");
assert.ok(createPage.includes("moderasi: ${moderation}"), "Create must expose API moderation status");
assert.ok(storiesPage.includes("moderasi: ${moderation}"), "Stories must expose API moderation status");
assert.ok(reelsPageParity.includes("Coba lagi"), "Reels API failure must offer retry");
assert.ok(reelsPageParity.includes("Media belum tersedia"), "Reels must explain unavailable media previews");
const feedViewParity = readFileSync(new URL("../components/reference-ui/FeedView.tsx", import.meta.url), "utf8");
const searchViewParity = readFileSync(new URL("../components/reference-ui/ExploreView.tsx", import.meta.url), "utf8");
const messagesViewParity = readFileSync(new URL("../components/reference-ui/MessagesView.tsx", import.meta.url), "utf8");
const searchRouteParity = readFileSync(new URL("../app/search/page.tsx", import.meta.url), "utf8");
const messagesRouteParity = readFileSync(new URL("../app/messages/page.tsx", import.meta.url), "utf8");
const marketplaceViewParity = readFileSync(new URL("../components/reference-ui/MarketplaceView.tsx", import.meta.url), "utf8");
const marketplaceRouteParity = readFileSync(new URL("../app/marketplace/page.tsx", import.meta.url), "utf8");
const cinemaViewParity = readFileSync(new URL("../components/reference-ui/AiCinemaView.tsx", import.meta.url), "utf8");
const cinemaRouteParity = readFileSync(new URL("../app/ai-cinema/page.tsx", import.meta.url), "utf8");
const visualSmoke = readFileSync(new URL("./visual-smoke.mjs", import.meta.url), "utf8");
const agentGoalsModal = readFileSync(new URL("../components/reference-ui/AgentGoalsTasksModal.tsx", import.meta.url), "utf8");
const agentIdentityModal = readFileSync(new URL("../components/reference-ui/AgentIdentityModal.tsx", import.meta.url), "utf8");
assert.ok(agentGoalsModal.includes("Agent Runtime API belum dihubungkan") && agentGoalsModal.includes("kontrak penyimpanan goal Agent belum dihubungkan"), "Agent Goals/Tasks UI must fail closed until canonical task/goal APIs are wired");
assert.doesNotMatch(agentGoalsModal, /setTimeout\(|Eksekusi otonom berhasil!|Tugas berhasil dihapus\.|Target strategis baru berhasil ditetapkan/);
const liveStageView = readFileSync(new URL("../components/reference-ui/LiveExperienceStage.tsx", import.meta.url), "utf8");
assert.doesNotMatch(liveStageView, /if \(!liveStateAvailable\)\s*\{\s*return\s*\(/, "Live unavailable state must preserve the copied source composition instead of swapping to a redesigned card");
assert.ok(liveStageView.includes("Belum ada presentasi aktif dari layanan Live Allpha.") && liveStageView.includes("disabled={!liveStateAvailable}"), "Live UI must preserve source layout while withholding sample slides and disabling unbound controls");
assert.doesNotMatch(liveStageView, /Takeover Mikrofon aktif: Human Owner mengambil alih siaran panggung|setTimeout\(/, "Live interactions must not simulate takeover success or timed activity");

const sourceStoryRail = feedViewParity.slice(feedViewParity.indexOf("{stories.map((story) => ("), feedViewParity.indexOf("{/* ========================================================================= */}", feedViewParity.indexOf("{stories.map((story) => (")) );
assert.ok(sourceStoryRail.includes("story.isAdd && onOpenCreateModal") && sourceStoryRail.includes("story.isLive && onOpenLiveStage") && sourceStoryRail.includes("story.id === 's-3d-world'"), "Story rail must preserve exactly the reference-defined Add/Live/3D actions");
assert.ok(sourceStoryRail.includes("onOpenStory"), "Public Story cards must connect to the canonical Story viewer route");

assert.ok(agentIdentityModal.includes("onSaveAgent(updated)") && agentIdentityModal.includes("AVATAR_3D_CATALOG"), "Agent Identity must preserve source catalog and delegate persistence to its adapter");

assert.ok(feedViewParity.includes("onRetry") && feedViewParity.includes("Coba lagi") && readFileSync(new URL("../app/feed/page.tsx", import.meta.url), "utf8").includes("loadFeed(true)"), "Feed error must offer canonical reload retry");
assert.ok(feedViewParity.includes("name: 'Tambah'") && feedViewParity.includes("productionMode\n    ? [{ id: 's-tambah'"), "Feed must preserve the source story-add card without seeding production story identities");
assert.ok(searchViewParity.includes("onRetrySearch") && searchViewParity.includes("onRetryTrends") && searchViewParity.includes("onRetryRecommendations") && searchRouteParity.includes("loadTrends()"), "Explore/Search error states must retry through canonical API loaders");
const allphaHubViewParity = readFileSync(new URL("../components/reference-ui/AllphaHubView.tsx", import.meta.url), "utf8");
assert.ok(searchViewParity.includes("AllphaHubView") && searchViewParity.includes("productionMode={productionMode}"), "Explore must retain the source PRD Hub section in production mode");
assert.ok(allphaHubViewParity.includes("productionMode ? [] : referenceStageEvents") && allphaHubViewParity.includes("productionMode ? [] : referenceVideotronSurfaces"), "PRD Hub must not show sample events or ad inventory in production");
assert.ok(allphaHubViewParity.includes("productionMode ? null : 1480") && allphaHubViewParity.includes("productionMode ? null : 620") && allphaHubViewParity.includes("creatorBalance == null ? '—'"), "PRD Hub must not show sample credit balances in production");
assert.ok(messagesViewParity.includes("onRetry") && messagesRouteParity.includes("void load()") && messagesRouteParity.includes("void open(active)"), "Messages list and conversation errors must offer retry");
assert.ok(marketplaceRouteParity.includes("catalogItems={[]}") && marketplaceRouteParity.includes("productionMode={true}") && marketplaceViewParity.includes("const PRODUCTS: ProductItem[] = catalogItems ?? []") && !marketplaceViewParity.includes("Allpha Holographic Cyber Hoodie") && !marketplaceViewParity.includes("MID-ALPH-2026"), "Marketplace production must use API-supplied catalog data and must not render seeded listings or simulated order IDs");
assert.ok(cinemaRouteParity.includes("catalogItems={[]}") && cinemaRouteParity.includes("productionMode={true}") && cinemaViewParity.includes("catalogItems ?? (productionMode ? [] : INITIAL_MOVIES_LIST)"), "AI Cinema production must not render reference demo films");
for (const route of ["/", "/login", "/start", "/account", "/feed", "/create", "/stories", "/reels", "/search", "/messages", "/spatial/navigation", "/spatial/themes", "/spatial/sample-scene", "/theme/sample-theme", "/ai-cinema", "/marketplace", "/live", "/ask-ai", "/profile", "/skill-challenges", "/content-studio", "/agents", "/agents/sample-agent/studio", "/agents/passport/sample-handle", "/communities", "/notifications", "/workflows"]) assert.ok(visualSmoke.includes(`"${route}"`), "Visual smoke must include canonical route: " + route);
assert.ok(visualSmoke.includes("27 routes × 4 viewports") && visualSmoke.includes("width: 360") && visualSmoke.includes("width: 390") && visualSmoke.includes("width: 820") && visualSmoke.includes("width: 1440"), "Visual smoke must cover every canonical Web route and all four viewport widths");
assert.ok(referenceNavbar.includes("onOpenNotifications"), "Navbar notifications must use a real navigation callback");
assert.doesNotMatch(referenceNavbar, /alert\(['"]Anda memiliki 3 notifikasi/);
if (existsSync(nativeContentPath)) assert.ok(nativeApp.includes('prefixes: ["allpha://"]'), "Native root deep-link prefix must be configured");


// UI-COPY-02 identity journey must use the source onboarding flow with real Auth/API boundaries.
const authRoute = readFileSync(new URL("../app/login/page.tsx", import.meta.url), "utf8");
const authAdapter = readFileSync(new URL("../components/reference-ui/AuthOnboardingRoute.tsx", import.meta.url), "utf8");
const authFlow = readFileSync(new URL("../components/reference-ui/AuthOnboardingFlow.tsx", import.meta.url), "utf8");
assert.ok(authRoute.includes("AuthOnboardingRoute"), "Login must use the reference onboarding adapter");
assert.ok(authAdapter.includes("supabase.auth.signUp") && authAdapter.includes("supabase.auth.signInWithPassword"), "Onboarding must use Supabase Auth");
assert.ok(authAdapter.includes('apiBase + "/v1/me"') && authAdapter.includes('apiBase + "/v1/me/profile"'), "Onboarding must provision and update canonical profile through FastAPI");
assert.ok(authAdapter.includes('apiBase + "/v1/agents"') && authAdapter.includes('method: "POST"'), "Agent creation must use canonical FastAPI");
assert.ok(authAdapter.includes('apiBase + "/v1/skill-catalog?limit=100&offset="'), "Agent Skill selection must use the canonical paginated catalog");
assert.ok(authFlow.includes("await onComplete(") && authFlow.includes("setStep('SUCCESS')"), "Onboarding success must follow awaited persistence");
assert.doesNotMatch(authFlow, /picsum\.photos|Bonus Selamat Datang: \+50 AI Credits|INITIAL_USER|INITIAL_AGENT/);
assert.ok(authFlow.includes("skillsLoading") && authFlow.includes("skillsError") && authFlow.includes("submissionError"), "Onboarding must expose loading and recoverable error states");



const liveStageRoute = readFileSync(new URL("../app/live/page.tsx", import.meta.url), "utf8");
const liveStageComponent = readFileSync(new URL("../components/reference-ui/LiveExperienceStage.tsx", import.meta.url), "utf8");
assert.ok(liveStageRoute.includes("liveStateAvailable={false}"), "Live Stage route must remain fail-closed until canonical session API is wired");
assert.ok(liveStageComponent.includes("Belum ada sesi atau pesan Live"), "Live Stage must show a canonical empty state rather than sample chat");
assert.doesNotMatch(liveStageComponent, /picsum\.photos|2430|3840|Raka Pratama/, "Live Stage must not seed demo viewers, likes or chat identities");


const askAiRoute = readFileSync(new URL("../app/ask-ai/page.tsx", import.meta.url), "utf8");
const askAiView = readFileSync(new URL("../components/reference-ui/AskAiView.tsx", import.meta.url), "utf8");
assert.ok(askAiRoute.includes('"/v1/me"') && askAiRoute.includes('"/v1/agents"'), "Ask AI route must load canonical identity and Agent catalog");
assert.ok(askAiView.includes("onSubmitQuery") && !askAiView.includes("/api/agent/interact"), "Ask AI must not bypass the canonical FastAPI Agent Runtime");
assert.ok(askAiView.includes("Belum ada percakapan dari Agent Runtime"), "Ask AI must expose an honest empty conversation state");


const profileRoute = readFileSync(new URL("../app/profile/page.tsx", import.meta.url), "utf8");
const profileView = readFileSync(new URL("../components/reference-ui/ProfileView.tsx", import.meta.url), "utf8");
assert.ok(profileRoute.includes('"/v1/me"') && profileRoute.includes('"/v1/agents"'), "Profile route must load canonical identity and Agent catalog");
assert.ok(!profileView.includes("const ownedAgents = [") && !profileView.includes("Brand 3D Vector") && !profileView.includes("0x7F2b"), "Profile must not seed demo Agents, skills, credits or ledger identity");
assert.ok(profileView.includes("showCredits && ag.credits != null"), "Profile credit values must only appear when canonical balances are supplied");

// Web PWA metadata and accessibility configuration are source-checked; installability still needs browser/device evidence.
const pwaManifest = readFileSync(new URL("../app/manifest.ts", import.meta.url), "utf8");
const webLayout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
assert.ok(pwaManifest.includes('display: "standalone"') && pwaManifest.includes('start_url: "/"') && pwaManifest.includes('scope: "/"'), "Web manifest must keep standalone PWA scope");
assert.ok(pwaManifest.includes('src: "/icon.svg"'), "Web manifest must reference the canonical app icon");
assert.ok(webLayout.includes("userScalable: true"), "Web viewport must preserve user zoom accessibility");

// WP-02: profile/settings must bind real canonical data and account mutations.
assert.ok(profileRoute.includes('/v1/me/profile-feed?limit=50'), "Profile must load the authenticated owner's published content through the canonical API");
const profileFeedApi = readFileSync(new URL("../../api/src/allpha_api/feed_api.py", import.meta.url), "utf8");
assert.ok(profileFeedApi.includes('@router.get("/v1/me/profile-feed"') && profileFeedApi.includes('user: dict[str, Any] = Depends(current_user)'), "Profile Feed must be protected by the canonical authenticated API");
assert.ok(profileFeedApi.includes('"owner_id": f"eq.{owner}"') && profileFeedApi.includes('"status": "eq.published"') && profileFeedApi.includes('"moderation_status": "eq.approved"'), "Profile Feed must be scoped to owner-published approved content");
assert.ok(profileFeedApi.includes('"engagement": {') && profileFeedApi.includes('"preview_url"'), "Profile Feed must return real engagement and signed media preview metadata");
assert.ok(profileRoute.includes('item.owner_id === me.user!.id'), "Profile feed must be scoped to the authenticated identity");
assert.ok(profileRoute.includes('/reaction') && profileRoute.includes('method: post.isLiked ? "DELETE" : "PUT"'), "Profile reactions must use canonical Feed mutation endpoints");
assert.ok(profileRoute.includes('onSelectPost={(post)=>{window.location.assign("/feed?content="+encodeURIComponent(post.id))}}'), "Selecting a profile post must open its canonical Feed detail");
assert.ok(profileRoute.includes('signOut({scope:"others"})') && profileRoute.includes('supabase.auth.signOut()'), "Profile session actions must use the configured Supabase Auth adapter");
assert.ok(profileView.includes('onOpenAccountSettings("settings")'), "Profile privacy must route to canonical account privacy controls");
assert.ok(profileView.includes('onOpenAccountSettings("profile")'), "Profile language preference must route to canonical profile settings");
assert.ok(profileView.includes('onRevokeOtherSessions') && profileView.includes('onLogout'), "Profile session actions must not claim success without auth callbacks");
assert.ok(profileRoute.includes('async function updateProfileAgent') && profileRoute.includes('method: "PATCH"') && profileRoute.includes('"/v1/agents/"'), "Profile Agent identity edits must persist through the canonical FastAPI Agent endpoint");
assert.ok(profileRoute.includes('"/skills"') && profileRoute.includes('"/knowledge/sources"') && profileRoute.includes('skill.status === "published"'), "Profile Agent summary must use canonical published Skills and Knowledge source endpoints");
assert.ok(profileRoute.includes('source.status === "ready" && source.latest_job?.status === "succeeded"'), "Profile Knowledge count must include only completed ready sources");
assert.ok(profileView.includes('onOpenAgentStudio') && profileView.includes('onOpenAgentPassport'), "Profile Agent runtime and public Passport actions must route to canonical pages");
assert.ok(profileView.includes('onOpenAgentRuntime') && profileRoute.includes('onOpenAgentRuntime={(agentId)=>{window.location.assign("/agents?agent="+encodeURIComponent(agentId))}}'), "Profile task actions must deep-link to the canonical Agent Runtime console");
const agentsRoute = readFileSync(new URL("../app/agents/page.tsx", import.meta.url), "utf8");
assert.ok(agentsRoute.includes('get("agent")') && agentsRoute.includes('scrollIntoView') && agentsRoute.includes('id={"agent-" + agent.id}'), "Agent Runtime console must honor the selected Agent deep link");
assert.ok(agentsRoute.includes('https://api.allpha.web.id') && agentStudioRoute.includes('https://api.allpha.web.id'), "Agent Runtime and Studio must use the canonical production API origin when no override is configured");
const agentStudioRoute = readFileSync(new URL("../app/agents/[agentId]/studio/page.tsx", import.meta.url), "utf8");
assert.ok(agentStudioRoute.includes('href="/workflows"') && agentStudioRoute.includes("/knowledge/retrieve") && agentStudioRoute.includes("/skills"), "Agent Studio must link the canonical Workflow Engine and expose Skill/Knowledge API integrations");
assert.ok(!profileView.includes('tasks?.length || 4'), "Profile must not fabricate a scheduled task count");
const agentIdentityModal = readFileSync(new URL("../components/reference-ui/AgentIdentityModal.tsx", import.meta.url), "utf8");
assert.ok(agentIdentityModal.includes("AI Gateway & Model Router") && !agentIdentityModal.includes("Gemini 2.5 Flash Allpha Gateway"), "Profile must defer provider/model selection to the canonical Model Router");
assert.ok(agentIdentityModal.includes('await onSaveAgent(updated)') && agentIdentityModal.includes('saving ? "Menyimpan…"'), "Agent profile modal must await canonical persistence before closing");
assert.ok(profileView.includes('{humanVerified && (') && !profileView.includes('className="absolute -bottom-1 -right-1 w-6 h-6 rounded-lg bg-[#0284C7] text-white flex items-center justify-center text-[10px] font-black border border-slate-900">\\n              ✓'), "Profile avatar must not show a verification badge without canonical verification");
assert.ok(profileView.includes("ag.status === 'active' ? 'bg-emerald-500' : ag.status === 'draft' ? 'bg-amber-400' : 'bg-slate-400'"), "Owned Agent status indicator must reflect canonical Agent status");
for (const demoMetric of ["142.840", "+24.8% bln ini", "489.200", "+38.1% bln ini", "+12.450", "18.2% conversion", "1.820 Sesi"]) assert.ok(!profileView.includes(demoMetric), `Profile analytics must not show fabricated metric: ${demoMetric}`);
assert.ok(!profileView.includes("Royalti Kreator: 85%") && !profileView.includes("Platform Fee (15%)"), "Profile financial panel must not invent unconfigured royalty/platform rates");
assert.ok(!profileView.includes("'Desain Grafis'") && !profileView.includes("'Auto-Reply Aktif'"), "Agent profile must not invent a category or claim runtime is active");
assert.ok(profileView.includes("Status runtime belum tersedia") && profileView.includes("Katalog Skills belum tersedia"), "Agent profile must expose unavailable runtime and Skill state honestly");
assert.ok(profileRoute.includes("isTakeoverActive={null}"), "Profile adapter must not assume takeover/runtime state without a canonical response");
assert.ok(!profileView.includes("setSettingsLang(lang.code as any)") && profileView.includes("Bahasa akun dikelola melalui formulir profil kanonis"), "Language preference must not report local-only selection as persisted");
const accountRoute = readFileSync(new URL("../app/account/page.tsx", import.meta.url), "utf8");
assert.ok(accountRoute.includes('new URLSearchParams(window.location.search).get("tab")'), "Account must support direct tab deep links");
assert.ok(accountRoute.includes('interestPreference') && accountRoute.includes('"not_interested"') && accountRoute.includes('updateInterestPreference'), "Web Social Graph must persist both positive and negative interest preferences");
assert.ok(accountRoute.includes('result.outcome === "follow_active"') && accountRoute.includes('result.outcome === "follow_request_created"'), "Web Social Graph must distinguish active follows from private-profile requests");
const apiMain = readFileSync(new URL("../../api/src/allpha_api/main.py", import.meta.url), "utf8");
assert.ok(apiMain.includes('def _social_edge_outcome') && apiMain.includes('"idempotent_replay": True') && apiMain.includes('return JSONResponse(status_code=200, content={'), "Social edge creation must return stable idempotent replay outcomes");
assert.ok(apiMain.includes('edge_filter = {') && apiMain.includes('"actor_user_id": f"eq.{user[\'id\']}"') && apiMain.includes('"target_user_id": f"eq.{payload.target_user_id}"'), "Social edge idempotency lookup must be actor- and target-scoped");
const nativeSocialSource = readFileSync(new URL("../../client/App.tsx", import.meta.url), "utf8");
assert.ok(nativeSocialSource.includes('updateInterestPreference') && nativeSocialSource.includes('"not_interested"'), "Native Social Graph must persist both positive and negative interest preferences");
assert.ok(nativeSocialSource.includes('result.outcome === "follow_active"') && nativeSocialSource.includes('result.outcome === "follow_request_created"'), "Native Social Graph must distinguish active follows from private-profile requests");
for (const contract of [
  "/v1/social/discover-users", "socialDiscoveryUsers", "socialDiscoveryRequestSequence.current",
  "Pencarian username menghormati pengaturan penemuan akun", "ID TARGET UNTUK BLOKIR / BISUKAN"
]) assert.ok(nativeSocialSource.includes(contract), "Native Social Graph must use privacy-aware username discovery: " + contract);
for (const tab of ["profile", "settings", "social", "consents"]) assert.ok(accountRoute.includes('"'+tab+'"'), `Account deep-link contract missing tab: ${tab}`);
const nativeApp = readFileSync(new URL("../../client/App.tsx", import.meta.url), "utf8");
for (const route of ["Profile: \"profile\"", "Account: \"account\"", "Agents: \"agents\"", "Feed: \"feed\"", "Reels: \"reels\"", "Stories: \"stories\"", "Search: \"search\"", "Messages: \"messages\"", "Notifications: \"notifications\"", "Communities: \"communities\""]) {
  assert.ok(nativeApp.includes(route), `Native deep-link route missing: ${route}`);
}
assert.ok(nativeApp.includes('tab?: "profile" | "settings" | "social" | "consents"'), "Native account route must accept canonical account tab parameters");


const messagesRoute = readFileSync(new URL("../app/messages/page.tsx", import.meta.url), "utf8");
for (const contract of ["authEventSeen", "sessionEpoch", "listSequence", "messageSequence", "sessionUserId", "client_message_id", "encodeURIComponent(c.id)"]) {
  assert.ok(messagesRoute.includes(contract), "Messages must isolate account sessions and guard stale requests: " + contract);
}
const notificationsRoute = readFileSync(new URL("../app/notifications/page.tsx", import.meta.url), "utf8");
for (const contract of ["authEventSeen", "sessionEpoch", "inboxSequence", "preferencesSequence", "sessionUserId", "encodeURIComponent(item.id)"]) {
  assert.ok(notificationsRoute.includes(contract), "Notifications must isolate account sessions and guard stale requests: " + contract);
}

const webNotifications = readFileSync(new URL("../app/notifications/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "sessionEpoch.current += 1", "inboxSequence.current += 1", "preferencesSequence.current += 1",
  "if (epoch !== sessionEpoch.current || sequence !== inboxSequence.current) return",
  "if (epoch === sessionEpoch.current && sequence === preferencesSequence.current)",
  "/v1/notifications/preferences", "/v1/notifications/read-all"
]) assert.ok(webNotifications.includes(contract), "Notifications must isolate account sessions and stale requests: " + contract);

for (const contract of [
  "sessionEpoch.current += 1", "listSequence.current += 1", "messageSequence.current += 1",
  "if(epoch!==sessionEpoch.current||sequence!==listSequence.current)return",
  "if(epoch!==sessionEpoch.current||sequence!==messageSequence.current)return",
  "client_message_id", "postgres_changes", "payload.detail?.message"
]) assert.ok(webMessages.includes(contract), "Messages must isolate account sessions and handle canonical API errors: " + contract);

const feedSessionIsolationSource = readFileSync(new URL("../app/feed/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "sessionEpoch.current += 1", "feedRequestSequence.current += 1", "preferencesRequestSequence.current += 1",
  "commentRequestSequence.current", "if (epoch !== sessionEpoch.current || sequence !== feedRequestSequence.current) return",
  "Sesi berubah; proses publikasi dihentikan."
]) assert.ok(feedSessionIsolationSource.includes(contract), "Feed must isolate sessions and stale interactions: " + contract);
assert.ok(apiMain.includes('follow_status = "requested" if target_profile.get("visibility") == "private" else "active"'), "Private profile follow must be persisted as requested, not rely on DB defaults");

const socialFeedLegacyFollowSource = readFileSync(new URL("../../api/src/allpha_api/feed_api.py", import.meta.url), "utf8");
assert.ok(socialFeedLegacyFollowSource.includes('follow_status = "requested" if target_profile.get("visibility") == "private" else "active"'), "Legacy follow endpoint must not bypass private-profile approval");

const sharedNavigationSource = readFileSync(new URL("../components/reference-ui/ReferenceNavigation.tsx", import.meta.url), "utf8");
for (const contract of ["authEventSeen", "indicatorRequestSequence.current", "refreshInboxIndicators(next)"]) {
  assert.ok(sharedNavigationSource.includes(contract), "Shared navigation must guard session-scoped inbox indicators: " + contract);
}

const accountSessionSource = readFileSync(new URL("../app/account/page.tsx", import.meta.url), "utf8");
const profileSessionSource = readFileSync(new URL("../app/profile/page.tsx", import.meta.url), "utf8");
for (const [name, source] of [["Account", accountSessionSource], ["Profile", profileSessionSource]]) {
  assert.ok(source.includes("authEventSeen") && source.includes("!authEventSeen"), name + " must not let a stale getSession read override a newer auth event");
}
