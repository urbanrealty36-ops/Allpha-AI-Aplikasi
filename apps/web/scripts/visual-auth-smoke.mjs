import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
const email = process.env.ALLPHA_E2E_EMAIL;
const password = process.env.ALLPHA_E2E_PASSWORD;
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
if (![supabaseUrl, publishableKey, email, password, apiBase].every(Boolean)) {
  throw new Error("Authenticated visual capture requires Supabase URL/key, dedicated E2E credentials, and API base URL secrets.");
}

const authResponse = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=password`, {
  method: "POST",
  headers: { apikey: publishableKey, "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
});
if (!authResponse.ok) throw new Error(`Supabase E2E sign-in failed with HTTP ${authResponse.status}; credentials are not logged.`);
const session = await authResponse.json();
assert.ok(session.access_token && session.refresh_token, "Supabase did not return a durable browser session");
const meResponse = await fetch(`${apiBase}/v1/me`, {
  headers: { Authorization: `Bearer ${session.access_token}`, Accept: "application/json" },
});
if (!meResponse.ok) throw new Error(`Authenticated FastAPI /v1/me check failed with HTTP ${meResponse.status}`);

const projectRef = new URL(supabaseUrl).hostname.split(".")[0];
const storageKey = `sb-${projectRef}-auth-token`;
const routes = ["/feed", "/agents", "/profile", "/workflows"];
const viewports = [
  { width: 360, height: 800, label: "mobile-360" },
  { width: 390, height: 844, label: "mobile-390" },
  { width: 820, height: 1000, label: "tablet-820" },
  { width: 1440, height: 1000, label: "desktop-1440" },
];
await mkdir("artifacts/reference-ui-authenticated", { recursive: true });
const browser = await chromium.launch({ headless: true });
const failures = [];
try {
  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    await page.addInitScript(({ key, authSession }) => {
      window.localStorage.setItem(key, JSON.stringify(authSession));
    }, { key: storageKey, authSession: session });
    for (const route of routes) {
      const response = await page.goto((process.env.ALLPHA_VISUAL_BASE_URL || "http://127.0.0.1:3000") + route,
        { waitUntil: "domcontentloaded", timeout: 45000 });
      await page.waitForTimeout(1200);
      const result = await page.evaluate((key) => ({
        width: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        bodyWidth: document.body?.scrollWidth ?? 0,
        sessionPresent: Boolean(JSON.parse(window.localStorage.getItem(key) || "null")?.access_token),
        bodyText: document.body?.innerText ?? "",
      }), storageKey);
      const record = { viewport: viewport.label, route, status: response?.status() ?? null,
        width: result.width, documentWidth: result.documentWidth, bodyWidth: result.bodyWidth,
        sessionPresent: result.sessionPresent };
      console.log(JSON.stringify(record));
      if (!response || response.status() >= 400) failures.push({ ...record, reason: "authenticated route returned HTTP 4xx/5xx" });
      if (!result.sessionPresent) failures.push({ ...record, reason: "browser session was not present" });
      if (/Konfigurasi autentikasi belum tersedia|Masuk terlebih dahulu untuk membuka/i.test(result.bodyText)) {
        failures.push({ ...record, reason: "route rendered unauthenticated/configuration fallback" });
      }
      if (result.documentWidth > viewport.width + 2 || result.bodyWidth > viewport.width + 2) {
        failures.push({ ...record, reason: "horizontal overflow" });
      }
      const routeSlug = route.replace(/^\/+/, "").replace(/\//g, "-") || "home";
      await page.screenshot({ path: `artifacts/reference-ui-authenticated/${routeSlug}-${viewport.label}.png`, fullPage: true });
    }
    await page.close();
  }
} finally {
  await browser.close();
}
if (failures.length) {
  console.error("AUTHENTICATED_VISUAL_FAILURES", JSON.stringify(failures, null, 2));
  process.exitCode = 1;
} else {
  console.log("Authenticated visual smoke passed: 4 routes × 4 viewports with Supabase session and FastAPI identity preflight.");
}
