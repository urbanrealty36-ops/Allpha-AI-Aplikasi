import assert from "node:assert/strict";
import { findInvalidMeshoptFallbackBuffers } from "../../../tools/3d-assets/meshopt-fallback-compat.mjs";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { readdirSync, readFileSync } from "node:fs";

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
const superAdmin = readFileSync(new URL("../../super-admin/app/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/admin/official-bots", "/v1/admin/official-bots/provision", "Siapkan kandidat", "Agency Agents · metadata-only", "catalog_source",
  "officialBotAction", "Aktifkan", "Stop", "Isolasi", "asset_validation_status"
]) assert.ok(superAdmin.includes(contract), `missing Super Admin Official Bot control contract: ${contract}`);
assert.doesNotMatch(superAdmin, /SUPABASE_SERVICE_ROLE_KEY|service_role/i);

// ENG-P13 Creator Studio + moderation contracts: authenticated API only; no mocked business records.
const contentStudio = readFileSync(new URL("../app/content-studio/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/content/mine", "/v1/content", "/media", "/preview", "/publish", "/retry",
  "Authorization", "session.access_token", "FormData", "preview_url", "visibility", "content_type",
  "Konten dikirim untuk ditinjau."
]) assert.ok(contentStudio.includes(contract), `missing ENG-P13 Web content contract: ${contract}`);
assert.doesNotMatch(contentStudio, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockContentItems|fakeFeed/);

const moderation = readFileSync(new URL("../../super-admin/app/content-moderation/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/content/admin/review-queue", "/v1/content/admin/", "expected_version",
  "Authorization", "access_token", "preview_url", "approve", "reject", "reason"
]) assert.ok(moderation.includes(contract), `missing ENG-P13 moderation contract: ${contract}`);
assert.doesNotMatch(moderation, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockModerationQueue/);

const nativeContent = readFileSync(new URL("../../client/App.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/content/mine", "/v1/content", "/media", "/preview", "/publish", "/retry",
  "Authorization", "session.access_token", "DocumentPicker", "FormData",
  "Draft konten tersimpan melalui FastAPI", "Konten dikirim untuk moderasi"
]) assert.ok(nativeContent.includes(contract), `missing ENG-P13 Native content contract: ${contract}`);
assert.doesNotMatch(nativeContent, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockContentItems|fakeFeed/);

const feedPage = readFileSync(new URL("../app/feed/page.tsx", import.meta.url), "utf8");
const feedPostCard = readFileSync(new URL("../components/feed/FeedPostCard.tsx", import.meta.url), "utf8");
const feedContract = feedPage + "\\n" + feedPostCard;
for (const contract of [
  "/v1/feed?", "/v1/feed/preferences", "/v1/feed/item/", "/reaction", "/save", "/comments", "/report", "/share",
  "personalization_enabled", "ranking_mode", "next_cursor", "Laporkan", "Bagikan", "reportReasons", "misinformation", "navigator.clipboard", "content"
]) assert.ok(feedContract.includes(contract), `missing ENG-P14 Web feed contract: ${contract}`);
assert.doesNotMatch(feedPage + feedPostCard, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockFeedItems|fakeFeed/);

const reportsPage = readFileSync(new URL("../../super-admin/app/content-reports/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/admin/content-reports", "/v1/admin/content-reports/", "platform:content.moderate",
  "dismiss", "hide_content", "Alasan keputusan", "Authorization", "preview_url", "media?.map"
]) assert.ok(reportsPage.includes(contract), `missing ENG-P14 Super Admin reports contract: ${contract}`);
assert.doesNotMatch(reportsPage, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockReports/);

const reelsPage = readFileSync(new URL("../app/reels/page.tsx", import.meta.url), "utf8");
for (const contract of [
  "/v1/reels?", "controls", "playsInline", "<audio", "preview_url", "toggleLike", "share(item)",
  "Masuk untuk menonton video pendek dan audio", "onError", "Perbarui tautan media dan coba lagi", "mediaErrors"
]) assert.ok(reelsPage.includes(contract), `missing ENG-P15 Web Reels contract: ${contract}`);
assert.doesNotMatch(reelsPage, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockReels|fakeReels/);
assert.ok(contentStudio.includes("audio/mpeg") && contentStudio.includes("<audio"), "Creator Studio must upload and preview audio");
const moderationPage = readFileSync(new URL("../../super-admin/app/content-moderation/page.tsx", import.meta.url), "utf8");
assert.ok(moderationPage.includes("<audio"), "Super Admin moderation must preview audio");
assert.ok(reportsPage.includes("<audio"), "Super Admin report review must preview audio");

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

 
// Reference feature routes: preserve truthful API-backed states and never import demo store data.
const cinemaPage = readFileSync(new URL("../app/cinema/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/content/mine", "/preview", "session.access_token", "preview_url", "Generator film AI dan job rendering khusus belum tersedia"]) {
  assert.ok(cinemaPage.includes(contract), `missing API-backed AI Cinema contract: ${contract}`);
}
assert.doesNotMatch(cinemaPage, /INITIAL_MOVIES_LIST|mockMovies|fakeCinemaItems|SUPABASE_SERVICE_ROLE_KEY|service_role/);

const livePage = readFileSync(new URL("../app/live/page.tsx", import.meta.url), "utf8");
for (const contract of ["Integrasi streaming belum tersedia", "belum menyediakan kontrak sesi live", "aria-disabled=\"true\"", 'href="/communities"', 'href="/messages"']) {
  assert.ok(livePage.includes(contract), `missing truthful Live Stage integration gate: ${contract}`);
}
assert.doesNotMatch(livePage, /2430|3840|setViewerCount|setLikesCount|mockLiveSession/);

const marketplacePage = readFileSync(new URL("../app/marketplace/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/skill-catalog?limit=50", "/v1/spatial/themes?limit=50", "Promise.allSettled", "kontrak commerce dan ledger", 'href="/agents"', 'href="/spatial/navigation"']) {
  assert.ok(marketplacePage.includes(contract), `missing API-backed Marketplace discovery contract: ${contract}`);
}
assert.doesNotMatch(marketplacePage, /priceCredits|priceIdr|mockMarketplaceItems|fakeMarketplace/);

const humanProfile = readFileSync(new URL("../app/profile/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/me", "/v1/me/profile", "session.access_token", "PATCH", "visibility", "Simpan profil", "role=\"alert\"", "Coba lagi"]) {
  assert.ok(humanProfile.includes(contract), `missing API-backed Human Profile contract: ${contract}`);
}
assert.doesNotMatch(humanProfile, /mockProfile|fakeProfile|SUPABASE_SERVICE_ROLE_KEY|service_role/);
const agentIdentityPage = readFileSync(new URL("../app/agents/page.tsx", import.meta.url), "utf8");
assert.ok(agentIdentityPage.includes('href="/profile"'), "Agent Identity must link to Human Profile");

const referenceNavigation = readFileSync(new URL("../components/reference-ui/ReferenceNavigation.tsx", import.meta.url), "utf8");
for (const contract of ['if (path.startsWith("/cinema")) return "FILM_AI"', 'if (path.startsWith("/live")) return "LIVESTAGE"', 'if (path.startsWith("/marketplace")) return "MARKETPLACE"', 'FILM_AI: "/cinema"', 'LIVESTAGE: "/live"', 'MARKETPLACE: "/marketplace"']) {
  assert.ok(referenceNavigation.includes(contract), `missing feature route mapping: ${contract}`);
}

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
  "Konten belum", "role=\"alert\"", "Konten belum tampil untuk publik."
]) assert.ok(webCreate.includes(contract), `missing Web Create lifecycle contract: ${contract}`);
for (const route of ['href="/feed"', 'href="/stories"', 'href="/reels"']) {
  assert.ok(webCreate.includes(route), `Create shell missing navigation link: ${route}`);
}
assert.doesNotMatch(webCreate, /SUPABASE_SERVICE_ROLE_KEY|service_role|mockContentItems|fakeFeed/);

const webFeed = readFileSync(new URL("../app/feed/page.tsx", import.meta.url), "utf8");
for (const route of ['href="/create"', 'href="/stories"', 'href="/reels"']) {
  assert.ok(webFeed.includes(route), `Feed shell missing navigation link: ${route}`);
}
for (const contract of ["/v1/feed", "/v1/feed/preferences", "session.access_token", "role=\"alert\""]) {
  assert.ok(webFeed.includes(contract), `missing Web Feed API/error contract: ${contract}`);
}
assert.doesNotMatch(webFeed, /mockFeedItems|fakeFeed/);

const webStories = readFileSync(new URL("../app/stories/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/stories", "/v1/content/", "/media", "/publish", "session.access_token", "FormData"]) {
  assert.ok(webStories.includes(contract), `missing Web Stories lifecycle contract: ${contract}`);
}
for (const route of ['href="/feed"', 'href="/create"', 'href="/reels"']) {
  assert.ok(webStories.includes(route), `Stories shell missing navigation link: ${route}`);
}
assert.doesNotMatch(webStories, /mockStories|fakeStoryItems/);

const webReels = readFileSync(new URL("../app/reels/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/reels", "/v1/feed/", "/reaction", "/share", "session.access_token"]) {
  assert.ok(webReels.includes(contract), `missing Web Reels API contract: ${contract}`);
}
for (const route of ['href="/feed"', 'href="/create"', 'href="/stories"']) {
  assert.ok(webReels.includes(route), `Reels shell missing navigation link: ${route}`);
}
assert.doesNotMatch(webReels, /mockReels|fakeReelItems/);

// Native parity must expose the same canonical content/story/feed capabilities;
// source assertions do not substitute for Expo typecheck or device acceptance.
for (const contract of [
  "/v1/content", "/v1/stories", "/v1/feed", "/v1/reels",
  "session.access_token", "DocumentPicker", "FormData"
]) assert.ok(nativeContent.includes(contract), `missing Native social/content parity contract: ${contract}`);


// Reference UI parity: active profile tab and profile action must target the
// canonical Human Profile route, not the AI Agent registry route.
const profileReferenceNavigation = readFileSync(new URL("../components/reference-ui/ReferenceNavigation.tsx", import.meta.url), "utf8");
assert.ok(profileReferenceNavigation.includes('if (path.startsWith("/profile")) return "PROFILE"'), "profile route must activate the Profile navigation item");
assert.ok(profileReferenceNavigation.includes('PROFILE: "/agents"'), "My Agent primary navigation must target the canonical Agent workspace");
assert.ok(profileReferenceNavigation.includes('if (path.startsWith("/profile")) return "PROFILE"'), "Human profile remains within the account navigation context");


// Explore has a stable reference-navigation route and delegates to the existing
// canonical search/trends/recommendations API page without sample data.
const exploreRoute = readFileSync(new URL("../app/explore/page.tsx", import.meta.url), "utf8");
assert.ok(exploreRoute.includes('"/v1/search?q="'), "Explore must use canonical FastAPI search");
assert.ok(exploreRoute.includes('"/v1/trends?limit=10"') && exploreRoute.includes('"/v1/recommendations?limit=8"'), "Explore must load canonical trends and recommendations");
const exploreReferenceNavigation = readFileSync(new URL("../components/reference-ui/ReferenceNavigation.tsx", import.meta.url), "utf8");
assert.ok(exploreReferenceNavigation.includes('path.startsWith("/search") || path.startsWith("/explore") || path.startsWith("/communities")'), "Explore/Search/Communities routes must activate Explore navigation");
assert.ok(exploreReferenceNavigation.includes('EXPLORE: "/explore"'), "Explore tab must open the Explore route");


// Canonical first-visit journey starts with Splash, then offers real Supabase
// sign-in/sign-up, then /start checks the canonical Agent identity before Feed.
const webEntry = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
for (const contract of ["showSplash ? <section", "Satu universe untuk manusia dan AI Agent.", 'setShowSplash(false); setMode("signin")', 'setShowSplash(false); setMode("signup")', 'supabase.auth.signInWithPassword', 'supabase.auth.signUp', 'window.location.assign("/start")']) {
  assert.ok(webEntry.includes(contract), "missing Splash/Auth journey contract: " + contract);
}
const webStart = readFileSync(new URL("../app/start/page.tsx", import.meta.url), "utf8");
assert.ok(webStart.includes('window.location.replace(hasAgentIdentity ? "/feed" : "/agents?onboarding=required")'), "authenticated journey must gate Feed on canonical Agent identity");


// Prevent reference-source inventory drift: every top-level reference UI
// component copied into the canonical isolated source folder must remain present.
const referenceComponents = [
  "AgentGoalsTasksModal.tsx", "AgentIdentityModal.tsx", "AiCinemaView.tsx",
  "AllphaHubView.tsx", "AskAiModal.tsx", "AskAiView.tsx",
  "AuthOnboardingFlow.tsx", "BottomNav.tsx", "CreatePostModal.tsx",
  "ExploreView.tsx", "FeedView.tsx", "GenerateModal.tsx",
  "LiveExperienceStage.tsx", "MarketplaceView.tsx", "MessagesView.tsx",
  "Navbar.tsx", "PostDetailView.tsx", "ProfileView.tsx", "ReelsView.tsx",
  "SkillsChallengeHub.tsx", "TakeoverControlView.tsx", "TakeoverModal.tsx",
  "ThreeWorldView.tsx", "Universe3DExperience.tsx", "Universe3DHubView.tsx"
];
const canonicalReferenceDirectory = new URL("../components/reference-ui/", import.meta.url);
const canonicalReferenceFiles = new Set(readdirSync(canonicalReferenceDirectory));
for (const component of referenceComponents) {
  assert.ok(canonicalReferenceFiles.has(component), "reference UI component missing from canonical source inventory: " + component);
}
assert.equal(referenceComponents.length, 25, "reference UI component inventory must cover all 25 top-level components");


// Explore and Messages must use real authenticated domain APIs, not reference demo stores.
const webExplore = readFileSync(new URL("../app/explore/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/search?q=", "/v1/trends?limit=10", "/v1/recommendations?limit=8", "/v1/skill-catalog?limit=6", "/v1/spatial/themes?limit=6", "session.access_token"]) {
  assert.ok(webExplore.includes(contract), "Explore missing canonical API contract: " + contract);
}
assert.doesNotMatch(webExplore, /SKILL_BLUEPRINTS_SAMPLE|INITIAL_POSTS|MEDIA_SURFACES_SAMPLE/);
const webMessages = readFileSync(new URL("../app/messages/page.tsx", import.meta.url), "utf8");
for (const contract of ["/v1/messages/conversations", "postgres_changes", "visibleItems.map", "aria-label=\"Cari percakapan\"", "aria-pressed={filter===t.id}"]) {
  assert.ok(webMessages.includes(contract), "Messages missing API/filter/realtime behavior: " + contract);
}


// PRD UI contract: primary mobile navigation, truthful status, no PWA-install or fake notification affordances.
const bottomNavigation = readFileSync(new URL("../components/reference-ui/BottomNav.tsx", import.meta.url), "utf8");
for (const contract of ['label: "Beranda"', 'label: "Explore"', 'label: "Buat"', 'label: "Pesan"', 'label: "My Agent"', 'aria-label="Navigasi utama"', 'aria-current={selected ? "page" : undefined}']) {
  assert.ok(bottomNavigation.includes(contract), "primary navigation contract missing: " + contract);
}
const referenceNavbar = readFileSync(new URL("../components/reference-ui/Navbar.tsx", import.meta.url), "utf8");
assert.doesNotMatch(referenceNavbar, /usePWAInstall|Install PWA|isInstallable|unreadMessagesCount = 2/);
assert.doesNotMatch(referenceNavbar, /w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white/);
assert.ok(feedPage.includes('onClick={() => void loadFeed(true)} disabled={loading || Boolean(busyKey)}'), "Feed error must expose a retry action");


// Error states must not masquerade as empty business data; retries must re-fetch canonical APIs.
const feedRetryPage = readFileSync(new URL("../app/feed/page.tsx", import.meta.url), "utf8");
assert.ok(feedRetryPage.includes('!loading && !error && items.length === 0'), "Feed error must not show a false empty state");
const agentWorkspace = readFileSync(new URL("../app/agents/page.tsx", import.meta.url), "utf8");
assert.ok(agentWorkspace.includes('onClick={() => session && void loadAgents(session)}'), "Agent workspace error must offer retry");
assert.ok(agentWorkspace.includes(': !error && agents.length === 0 ?'), "Agent API errors must not be shown as no Agent exists");
const storiesPage = readFileSync(new URL("../app/stories/page.tsx", import.meta.url), "utf8");
assert.ok(storiesPage.includes('!error && active.length === 0'), "Stories API errors must not be shown as an empty active feed");
assert.ok(storiesPage.includes('!loading && !error && mine.length === 0'), "Stories API errors must not be shown as an empty owned list");


// Reels comments must use canonical feed comment endpoints, not reference alert/sample interactions.
const reelsInteractions = readFileSync(new URL("../app/reels/page.tsx", import.meta.url), "utf8");
for (const contract of [
  '"/v1/feed/" + encodeURIComponent(item.id) + "/comments?limit=30"',
  '"/v1/feed/" + encodeURIComponent(item.id) + "/comments"',
  "toggleComments", "submitComment", "commentsLoading", "commentsErrors",
  "aria-expanded={Boolean(commentsOpen[item.id])}", "maxLength={2000}"
]) {
  assert.ok(reelsInteractions.includes(contract), "Reels comment interaction contract missing: " + contract);
}
assert.doesNotMatch(reelsInteractions, /alert\(|mockReels|fakeReels/);


// Agent workspace must render the same first frame on the server and during hydration.
assert.ok(agents.includes("const [mounted, setMounted] = useState(false)"));
assert.ok(agents.includes("if (!mounted) return <main className=\\"identity-shell\\"><section className=\\"config-card\\" role=\\"status\\">Memeriksa sesi identitas Agent…</section></main>;"));


// The shared shell owns global navigation; Create must not render a duplicate header or bottom bar.
const createRoute = readFileSync(new URL("../app/create/page.tsx", import.meta.url), "utf8");
assert.doesNotMatch(createRoute, /ReferenceNavigation|BottomNav|<Navbar/);
