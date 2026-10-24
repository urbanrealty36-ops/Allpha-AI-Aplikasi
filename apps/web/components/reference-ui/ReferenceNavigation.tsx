"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const primary = [
  { href: "/feed", label: "Beranda", glyph: "⌂" },
  { href: "/search", label: "Jelajahi", glyph: "⌕" },
  { href: "/create", label: "Buat", glyph: "+" },
  { href: "/reels", label: "Reels", glyph: "▷" },
  { href: "/messages", label: "Pesan", glyph: "◌" },
  { href: "/agents", label: "My Agent", glyph: "◇" },
];

const desktop = [
  { href: "/feed", label: "Konten" },
  { href: "/agents", label: "AI Agent" },
  { href: "/spatial/navigation", label: "3D Universe" },
  { href: "/communities", label: "Komunitas" },
  { href: "/skill-challenges", label: "Skills" },
  { href: "/workflows", label: "Workflows" },
];

export default function ReferenceNavigation() {
  const pathname = usePathname() || "/feed";
  const isActive = (href: string) =>
    pathname === href || (href !== "/feed" && pathname.startsWith(href + "/"));

  return (
    <>
      <header className="allpha-ref-navbar">
        <Link href="/feed" className="allpha-ref-brand" aria-label="Allpha Universe beranda">
          <span className="allpha-ref-mark">A</span>
          <span className="allpha-ref-brand-copy"><strong>ALLPHA</strong><small>UNIVERSE</small></span>
        </Link>
        <label className="allpha-ref-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="Cari konten, AI Agent, dan Universe"
            placeholder="Cari konten, AI Agent, atau District 3D..."
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                const value = (event.currentTarget as HTMLInputElement).value.trim();
                if (value.length >= 2) window.location.assign("/search?q=" + encodeURIComponent(value));
              }
            }}
          />
        </label>
        <nav className="allpha-ref-top-links" aria-label="Jelajah Allpha">
          {desktop.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
              className={isActive(item.href) ? "is-active" : ""}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <Link href="/messages" className="allpha-ref-top-action" aria-label="Buka pesan">◌</Link>
      </header>
      <nav className="allpha-ref-bottom-nav" aria-label="Navigasi utama">
        {primary.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={"allpha-ref-nav-item" + (active ? " is-active" : "")}
            >
              <span className={"allpha-ref-nav-glyph" + (item.href === "/create" ? " is-create" : "")}>{item.glyph}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
