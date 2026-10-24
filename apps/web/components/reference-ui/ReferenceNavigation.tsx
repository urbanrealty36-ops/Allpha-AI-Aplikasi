"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const primary = [
  { href: "/feed", label: "Beranda", glyph: "⌂" },
  { href: "/explore", label: "Explore", glyph: "⌕" },
  { href: "/create", label: "Buat", glyph: "+" },
  { href: "/reels", label: "Reels", glyph: "▷" },
  { href: "/messages", label: "Pesan", glyph: "◌" },
  { href: "/agents", label: "My Agent", glyph: "◇" },
];

export default function ReferenceNavigation() {
  const pathname = usePathname() || "/feed";
  return (
    <>
      <header className="allpha-ref-navbar">
        <Link href="/feed" className="allpha-ref-brand" aria-label="Allpha Universe beranda">
          <span className="allpha-ref-mark">A</span>
          <span className="allpha-ref-brand-copy"><strong>ALLPHA</strong><small>UNIVERSE</small></span>
        </Link>
        <label className="allpha-ref-search">
          <span aria-hidden="true">⌕</span>
          <input aria-label="Cari konten dan AI Agent" placeholder="Cari konten, AI Agent, atau District 3D..." onKeyDown={(event) => {
            if (event.key === "Enter") window.location.assign("/explore?q=" + encodeURIComponent((event.currentTarget as HTMLInputElement).value));
          }} />
        </label>
        <Link href="/messages" className="allpha-ref-top-action" aria-label="Buka pesan">◌</Link>
      </header>
      <nav className="allpha-ref-bottom-nav" aria-label="Navigasi utama">
        {primary.map((item) => {
          const active = pathname === item.href || (item.href !== "/feed" && pathname.startsWith(item.href + "/"));
          return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={"allpha-ref-nav-item" + (active ? " is-active" : "")}>
            <span className={"allpha-ref-nav-glyph" + (item.href === "/create" ? " is-create" : "")}>{item.glyph}</span>
            <span>{item.label}</span>
          </Link>;
        })}
      </nav>
    </>
  );
}
