import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const REQUIRED_ASSETS = [
  { path: "/asset-manifest.json", contentType: "application/json" },
  { path: "/icon.svg", contentType: "image/svg+xml" },
  { path: "/assets/slides/slide_welcome_3d_1793022854882.jpg", contentType: "image/jpeg" },
  { path: "/assets/slides/slide_cinema_3d_1793023017033.jpg", contentType: "image/jpeg" },
  { path: "/assets/slides/slide_livestage_3d_1793023043430.jpg", contentType: "image/jpeg" },
  // Spatial preview assets are intentionally excluded: middleware returns 404
  // while the 3D Universe is globally locked. They must not fail app readiness.
] as const;

export async function GET() {
  const port = process.env.PORT || "3000";
  const origin = `http://127.0.0.1:${port}`;
  const checks = await Promise.all(REQUIRED_ASSETS.map(async (asset) => {
    try {
      const response = await fetch(`${origin}${asset.path}`, {
        method: "HEAD",
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
      const contentType = response.headers.get("content-type") || "";
      const ok = response.ok && contentType.toLowerCase().startsWith(asset.contentType);
      return {
        path: asset.path,
        ok,
        status: response.status,
        content_type: contentType,
      };
    } catch {
      return {
        path: asset.path,
        ok: false,
        status: 0,
        content_type: null,
        error: "ASSET_PROBE_FAILED",
      };
    }
  }));

  const failed = checks.filter((check) => !check.ok);
  return NextResponse.json({
    status: failed.length === 0 ? "ok" : "degraded",
    asset_count: checks.length,
    failed_count: failed.length,
    assets: checks,
  }, {
    status: failed.length === 0 ? 200 : 503,
    headers: { "Cache-Control": "no-store" },
  });
}
