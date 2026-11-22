import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const baseUrl = process.env.ALLPHA_VISUAL_BASE_URL || "http://127.0.0.1:3000";
const routes = ["/", "/welcome", "/login", "/register", "/start", "/account", "/feed", "/create", "/stories", "/reels", "/search", "/messages", "/spatial/navigation", "/spatial/themes", "/spatial/sample-scene", "/theme/sample-theme", "/ai-cinema", "/marketplace", "/live", "/ask-ai", "/profile", "/skill-challenges", "/content-studio", "/agents", "/agents/sample-agent/studio", "/agents/passport/sample-handle", "/communities", "/notifications", "/workflows"];
const viewports = [
  { width: 360, height: 800, label: "mobile-360" },
  { width: 390, height: 844, label: "mobile-390" },
  { width: 820, height: 1000, label: "tablet-820" },
  { width: 1440, height: 1000, label: "desktop-1440" },
];

await mkdir("artifacts/reference-ui-visual", { recursive: true });
const browser = await chromium.launch({ headless: true });
const failures = [];
try {
  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    for (const route of routes) {
      const response = await page.goto(baseUrl + route, { waitUntil: "domcontentloaded", timeout: 45000 });
      await page.waitForTimeout(900);
      const result = await page.evaluate(() => ({
        width: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        bodyWidth: document.body?.scrollWidth ?? 0,
        title: document.title,
        bodyText: document.body?.innerText ?? "",
        headerText: document.querySelector("header")?.innerText ?? "",
      }));
      const record = { viewport: viewport.label, route, status: response?.status() ?? null, ...result };
      console.log(JSON.stringify(record));
      if (!response || response.status() >= 400) failures.push({ ...record, reason: "HTTP 4xx/5xx or navigation failure" });
      if (route === "/welcome" && /Slide Sapa & Panduan|Login \/ Register|Buka Feed Aplikasi/.test(result.headerText)) {
        failures.push({ ...record, reason: "Splash header still contains removed action buttons" });
      }
      if (route === "/login" && (!result.bodyText.toLowerCase().includes("masuk ke human identity") || result.bodyText.toLowerCase().includes("nama lengkap"))) {
        failures.push({ ...record, reason: "Login route is rendering registration-only fields" });
      }
      if (route === "/register" && (!result.bodyText.toLowerCase().includes("registrasi human identity") || !result.bodyText.toLowerCase().includes("nama lengkap"))) {
        failures.push({ ...record, reason: "Register route is missing Human identity fields" });
      }
      if (result.documentWidth > viewport.width + 2 || result.bodyWidth > viewport.width + 2) {
        failures.push({ ...record, reason: "horizontal overflow" });
      }
      const routeSlug = route.replace(/^\/+/, "").replace(/\//g, "-") || "home";
      await page.screenshot({
        path: `artifacts/reference-ui-visual/${routeSlug}-${viewport.label}.png`,
        fullPage: true,
      });
    }
    await page.close();
  }

  // Functional navigation regression: verify real client-side actions, not only HTTP route availability.
  const interactionPage = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  try {
    await interactionPage.goto(baseUrl + "/feed", { waitUntil: "domcontentloaded", timeout: 45000 });
    await interactionPage.getByRole("button", { name: "Buka halaman awal Allpha" }).click();
    await interactionPage.waitForURL((url) => url.pathname === "/welcome", { timeout: 10000 });
    console.log(JSON.stringify({ interaction: "header-brand-navigation", result: "passed", pathname: new URL(interactionPage.url()).pathname }));

    await interactionPage.goto(baseUrl + "/feed", { waitUntil: "domcontentloaded", timeout: 45000 });
    await interactionPage.getByRole("button", { name: /Film AI/ }).click();
    await interactionPage.waitForURL((url) => url.pathname === "/ai-cinema", { timeout: 10000 });
    console.log(JSON.stringify({ interaction: "bottom-nav-film-ai", result: "passed", pathname: new URL(interactionPage.url()).pathname }));

    await interactionPage.goto(baseUrl + "/feed", { waitUntil: "domcontentloaded", timeout: 45000 });
    await interactionPage.getByRole("button", { name: "Search" }).click();
    const searchInput = interactionPage.getByPlaceholder("Cari konten, agent, district 3D...");
    await searchInput.fill("uji navigasi");
    await searchInput.press("Enter");
    await interactionPage.waitForURL((url) => url.pathname === "/search" && url.searchParams.get("q") === "uji navigasi", { timeout: 10000 });
    console.log(JSON.stringify({ interaction: "header-search-submit", result: "passed", pathname: new URL(interactionPage.url()).pathname }));

    await interactionPage.goto(baseUrl + "/feed", { waitUntil: "domcontentloaded", timeout: 45000 });
    await interactionPage.getByRole("button", { name: "Pesan" }).click();
    await interactionPage.waitForURL((url) => url.pathname === "/messages", { timeout: 10000 });
    console.log(JSON.stringify({ interaction: "header-messages-navigation", result: "passed", pathname: new URL(interactionPage.url()).pathname }));
  } catch (error) {
    failures.push({ interaction: "global-navigation", reason: error instanceof Error ? error.message : String(error) });
  } finally {
    await interactionPage.close();
  }
} finally {
  await browser.close();
}
if (failures.length) {
  console.error("VISUAL_SMOKE_FAILURES", JSON.stringify(failures, null, 2));
  process.exitCode = 1;
} else {
  console.log("Visual route smoke passed: 29 routes × 4 viewports; screenshots captured for every route.");
}
