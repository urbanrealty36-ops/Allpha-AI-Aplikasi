import { notFound } from "next/navigation";
import type { ReactNode } from "react";

/**
 * Spatial/3D Universe is intentionally inaccessible to all visitors while
 * the domain is under development. A route-level server boundary ensures
 * anonymous and authenticated requests receive the same not-found response.
 */
export default function SpatialLockedLayout({ children }: { children: ReactNode }) {
  void children;
  notFound();
}
