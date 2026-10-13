import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Allpha Super Admin — Operations", description: "Operational foundation for Allpha platform administrators." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="id"><body>{children}</body></html>; }
