import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const baseUrl = process.env.ALLPHA_VISUAL_BASE_URL || "http://127.0.0.1:3000";
const routes = ["/", "/login", "/start", "/account", "/feed", "/create", "/stories", "/reels", "/search", "/messages", "/spatial/navigation", "/spatial/navigation/catalog", "/spatial/themes", "/spatial/sample-scene", "/theme/sample-theme", "/ai-cinema", "/marketplace", "/live", "/ask-ai", "/profile", "/skill-challenges", "/content-studio", "/agents", "/agents/sample-agent/studio", "/agents/passport/sample-handle", "/communities", "/notifications", "/workflows"];
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
      }));
      const record = { viewport: viewport.label, route, status: response?.status() ?? null, ...result };
      console.log(JSON.stringify(record));
      if (!response || response.status() >= 400) failures.push({ ...record, reason: "HTTP 4xx/5xx or navigation failure" });
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
} finally {
  await browser.close();
}
if (failures.length) {
  console.error("VISUAL_SMOKE_FAILURES", JSON.stringify(failures, null, 2));
  process.exitCode = 1;
} else {
  console.log("Visual route smoke passed: 28 routes × 4 viewports; screenshots captured for every route.");
}
