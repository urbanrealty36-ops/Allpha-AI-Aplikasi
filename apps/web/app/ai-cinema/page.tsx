"use client";

import { useEffect, useState } from "react";
import AiCinemaView, { AiMovieItem } from "../../components/reference-ui/AiCinemaView";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type CatalogTitle = {
  id: string; title: string; original_title?: string | null; genre: string; synopsis: string;
  language_code: string; maturity_rating: string; credits: Array<{ role?: string; name?: string; agent_id?: string }>;
  cover_media_id?: string | null; trailer_media_id?: string | null; published_at?: string | null;
};

const genreMap: Record<string, AiMovieItem["genre"]> = {
  c_drama: "C_DRAMA", k_drama: "K_DRAMA", scifi: "SCIFI", romance: "ROMANCE",
  thriller: "THRILLER", animation_3d: "ANIMATION_3D",
};

export default function AiCinemaPage() {
  const [items, setItems] = useState<AiMovieItem[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void fetch(apiBase + "/v1/cinema/catalog?limit=24", { cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error("catalog unavailable");
        const data = await response.json();
        const mapped: AiMovieItem[] = (Array.isArray(data?.items) ? data.items as CatalogTitle[] : []).map(item => {
          const producer = item.credits?.find(credit => credit.role === "producer" || credit.role === "director");
          return {
            id: item.id,
            title: item.title,
            originalTitle: item.original_title ?? undefined,
            genre: genreMap[item.genre] ?? "ALL",
            genreLabel: item.genre.replaceAll("_", " "),
            coverImage: "",
            bannerImage: "",
            episodesCount: 0,
            totalViews: "",
            rating: 0,
            durationPerEp: "",
            releaseYear: item.published_at ? new Date(item.published_at).getFullYear().toString() : "",
            producerHuman: { name: producer?.name ?? "Kreator", handle: "", avatar: "" },
            aiCoDirector: { name: "Kolaborator AI", handle: "", avatar: "", specialty: "" },
            synopsis: item.synopsis,
            aiTechStack: "",
            creatorMonthlyEarningsCredits: 0,
          };
        });
        if (active) { setItems(mapped); setState("ready"); }
      })
      .catch(() => { if (active && !controller.signal.aborted) { setItems([]); setState("unavailable"); } });
    return () => { active = false; controller.abort(); };
  }, []);

  return <AiCinemaView userCredits={null} catalogItems={items} catalogState={state} productionMode />;
}
