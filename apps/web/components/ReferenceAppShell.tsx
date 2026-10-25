"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import ReferenceNavigation from "./reference-ui/ReferenceNavigation";
import ReferenceFeedChrome from "./reference-ui/ReferenceFeedChrome";

export default function ReferenceAppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const hideNavigation = pathname === "/" || pathname === "/start";

  return (
    <>
      {!hideNavigation && <ReferenceNavigation />}
      <div className={!hideNavigation ? "allpha-reference-app-content" : undefined}>{pathname === "/feed" && <ReferenceFeedChrome />}{children}</div>
    </>
  );
}
