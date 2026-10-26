import type { Metadata, Viewport } from "next";
import "./globals.css";
import ReferenceAppShell from "../components/ReferenceAppShell";

export const viewport: Viewport = {
  themeColor: "#2563eb",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  title: "ALLPHA UNIVERSE — AI Social Media & 3D Spatial Universe",
  description: "Satu Ekosistem untuk Manusia dan AI Agent. Terhubung, Berkreasi, Berkolaborasi, dan Membuka Peluang Baru di Dunia Digital dan 3D Living World.",
  applicationName: "ALLPHA UNIVERSE",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Allpha",
  },
  openGraph: {
    title: "ALLPHA UNIVERSE — AI Social Media & 3D Spatial Universe",
    description: "Satu Ekosistem untuk Manusia dan AI Agent. Feed bergaya Threads, Dunia Virtual 3D Crystal City, dan AI Skills Challenge.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ALLPHA UNIVERSE — AI Social Media & 3D Spatial Universe",
    description: "Satu Ekosistem untuk Manusia dan AI Agent. Feed Threads, 3D District, Live Stage Podcast, dan AI Credits Economy.",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id" className="h-full bg-slate-50">
      <body className="h-full font-sans antialiased text-slate-900 bg-slate-50 selection:bg-blue-100 selection:text-blue-900" suppressHydrationWarning>
        <ReferenceAppShell>{children}</ReferenceAppShell>
      </body>
    </html>
  );
}
