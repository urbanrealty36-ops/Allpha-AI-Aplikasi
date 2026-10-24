import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright";

const baseUrl = process.env.ALLPHA_UI_BASE_URL || "http://127.0.0.1:3100";
const outDir = process.env.ALLPHA_UI_ARTIFACTS || ".artifacts/ui-responsive";
const viewports = [
  { width: 360, height: 800, label: "mobile-360" },
  { width: 390, height: 844, label: "mobile-390" },
  { width: 820, height: 1180, label: "tablet-820" },
  { width: 1440, height: 1000, label: "desktop-1440" },
];
const routes = [
  "/feed", "/explore", "/search", "/reels", "/profile", "/agents", "/messages",
  "/stories", "/create", "/posts/ui-responsive-smoke", "/cinema", "/live",
  "/marketplace", "/communities", "/notifications", "/spatial/navigation",
  "/spatial/themes",
];
fs.mkdirSync(outDir, { recursive: true });
const server = spawn("npm", ["run", "start", "--", "--hostname", "127.0.0.1", "--port", "3100"], {
  cwd: process.cwd(), stdio: "ignore", env: process.env,
});
let browser;
const results = [];
try {
  let ready = false;
  for (let i = 0; i < 60; i++) {
    try {
      const response = await fetch(baseUrl + "/feed");
      if (response.ok) { ready = true; break; }
    } catch {}
    await delay(500);
  }
  assert.ok(ready, "Next.js production server did not become ready");
  browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });

  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    for (const route of routes) {
      const page = await context.newPage();
      const pageErrors = [];
      page.on("pageerror", error => pageErrors.push(String(error)));
      let responseStatus = null;
      try {
        const response = await page.goto(baseUrl + route, { waitUntil: "domcontentloaded", timeout: 25000 });
        responseStatus = response?.status() ?? null;
        await page.waitForTimeout(350);
        const metrics = await page.evaluate(() => ({
          viewportWidth: window.innerWidth,
          documentWidth: document.documentElement.scrollWidth,
          bodyWidth: document.body.scrollWidth,
          mainCount: document.querySelectorAll("main").length,
          horizontalOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > window.innerWidth + 1,
          visiblePrimaryNav: Boolean(document.querySelector('nav[aria-label="Navigasi utama"]')),
        }));
        const result = { route, viewport: viewport.label, responseStatus, ...metrics, pageErrors };
        results.push(result);
        assert.equal(responseStatus, 200, route + " should return HTTP 200 at " + viewport.label);
        assert.equal(metrics.horizontalOverflow, false, route + " has horizontal overflow at " + viewport.label + ": " + JSON.stringify(metrics));
        assert.equal(pageErrors.length, 0, route + " emitted browser errors at " + viewport.label + ": " + pageErrors.join("; "));
        if (route !== "/spatial/navigation" && route !== "/posts/ui-responsive-smoke") {
          assert.equal(metrics.mainCount > 0, true, route + " must render main content");
        }
        if (viewport.width <= 390 && !["/spatial/navigation", "/posts/ui-responsive-smoke"].includes(route)) {
          assert.equal(metrics.visiblePrimaryNav, true, route + " should retain primary mobile navigation");
        }
        const screenshotPath = path.join(outDir, viewport.label + route.replaceAll("/", "_") + ".png");
        await page.screenshot({ path: screenshotPath, fullPage: true, animations: "disabled", timeout: 15000 }).catch(error => {
          results[results.length - 1].screenshotError = String(error);
        });
      } catch (error) {
        if (!results.some(result => result.route === route && result.viewport === viewport.label)) {
          results.push({ route, viewport: viewport.label, responseStatus, error: String(error), pageErrors });
        }
        throw error;
      } finally {
        await page.close();
      }
    }
    await context.close();
  }
  const summary = {
    test: "Allpha Web responsive route smoke",
    routes: routes.length,
    viewports: viewports.map(({ width, height, label }) => ({ width, height, label })),
    total: results.length,
    passed: results.filter(result => !result.error && result.responseStatus === 200 && !result.horizontalOverflow && !(result.pageErrors?.length)).length,
    failed: results.filter(result => result.error || result.responseStatus !== 200 || result.horizontalOverflow || result.pageErrors?.length).length,
    screenshots: fs.readdirSync(outDir).filter(name => name.endsWith(".png")).length,
    scope: "Unauthenticated route shell, responsive overflow, primary mobile navigation and browser runtime errors. Authenticated user journeys and production API behavior require separate acceptance.",
    results,
  };
  fs.writeFileSync(path.join(outDir, "summary.json"), JSON.stringify(summary, null, 2));
  console.log(JSON.stringify({ ...summary, results: undefined }, null, 2));
  if (summary.failed) process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
}
