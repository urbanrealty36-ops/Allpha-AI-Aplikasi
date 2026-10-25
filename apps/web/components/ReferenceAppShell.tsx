"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import ReferenceNavigation from "./reference-ui/ReferenceNavigation";

export default function ReferenceAppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const hideNavigation = pathname === "/" || pathname === "/start" || pathname === "/login";

  return (
    <>
      {!hideNavigation && <ReferenceNavigation />}
      <div className={!hideNavigation ? "allpha-reference-app-content" : undefined}>{children}</div>
    </>
  );
}
