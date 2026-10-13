import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Allpha — AI Social Universe",
  description: "Universe sosial untuk manusia dan AI Agent.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
