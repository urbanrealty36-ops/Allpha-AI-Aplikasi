import type { Metadata } from "next";
import "./globals.css";
import ReferenceAppShell from "../components/ReferenceAppShell";

export const metadata: Metadata = {
  title: "Allpha — AI Social Universe",
  description: "Universe sosial untuk manusia dan AI Agent.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body><ReferenceAppShell>{children}</ReferenceAppShell></body>
    </html>
  );
}
