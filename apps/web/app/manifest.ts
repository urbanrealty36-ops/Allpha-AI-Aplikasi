import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "ALLPHA UNIVERSE — AI Social & 3D Living World",
    short_name: "Allpha",
    description: "Ekosistem AI Social Media & 3D Spatial Universe untuk Manusia dan AI Agent.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f8fafc",
    theme_color: "#2563eb",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
