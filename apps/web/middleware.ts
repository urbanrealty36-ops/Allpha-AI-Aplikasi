import { NextRequest, NextResponse } from "next/server";

/**
 * Defense-in-depth for public static Spatial preview assets.
 * The Spatial route layouts and FastAPI lock remain the primary domain gates.
 */
export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const locked =
    pathname.startsWith("/assets/menggu3d/") ||
    pathname === "/assets/reference-source/images/menggu_district_spatial_1793024717088.jpg";

  if (locked) {
    return new NextResponse(null, {
      status: 404,
      headers: {
        "Cache-Control": "no-store",
        "X-Allpha-Spatial-Access": "locked",
      },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/assets/menggu3d/:path*",
    "/assets/reference-source/images/menggu_district_spatial_1793024717088.jpg",
  ],
};
