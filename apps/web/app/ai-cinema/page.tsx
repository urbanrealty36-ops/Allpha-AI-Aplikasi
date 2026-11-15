"use client";

import { useEffect, useState } from "react";
import AiCinemaView, { AiMovieItem } from "../../components/reference-ui/AiCinemaView";
import AiCinemaCreatorWorkspace from "../../components/ai-cinema/AiCinemaCreatorWorkspace";
import AiCinemaPlaybackPanel from "../../components/ai-cinema/AiCinemaPlaybackPanel";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type CatalogTitle = {
  id: string; title: string; original_title?: string | null; genre: string; synopsis: string;
  language_code: string; maturity_rating: string; credits: Array<{ role?: string; name?: string; agent_id?: string }>;
  cover_media_id?: string | null; trailer_media_id?: string | null; published_at?: string | null;
  episodes_count?: number; cover_preview_url?: string | null; trailer_preview_url?: string | null;
  status?: string; moderation_status?: string; rights_status?: string;
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
          const credits = Array.isArray(item.credits) ? item.credits : [];
          const producer = credits.find(credit => credit.contributor_type === "human" && (credit.role === "producer" || credit.role === "director"))
            ?? credits.find(credit => credit.contributor_type === "human");
          const aiCoDirector = credits.find(credit => credit.contributor_type === "agent" && (credit.role === "co_director" || credit.role === "director"))
            ?? credits.find(credit => credit.contributor_type === "agent");
          const cover = item.cover_preview_url ?? "";
          const banner = item.trailer_preview_url ?? cover;
          return {
            id: item.id,
            title: item.title,
            originalTitle: item.original_title ?? undefined,
            genre: genreMap[item.genre] ?? "ALL",
            genreLabel: item.genre.replaceAll("_", " "),
            coverImage: cover,
            bannerImage: banner,
            episodesCount: Number.isInteger(item.episodes_count) ? item.episodes_count! : 0,
            totalViews: "Belum tersedia",
            rating: null,
            durationPerEp: "Lihat durasi episode",
            releaseYear: item.published_at ? new Date(item.published_at).getFullYear().toString() : "",
            producerHuman: { name: producer?.attribution_label ?? producer?.name ?? "Kreator belum dicantumkan", handle: "", avatar: "" },
            aiCoDirector: { name: aiCoDirector?.attribution_label ?? aiCoDirector?.name ?? "AI collaborator belum dicantumkan", handle: "", avatar: "", specialty: "" },
            synopsis: item.synopsis,
            aiTechStack: "",
            creatorMonthlyEarningsCredits: null,
            verificationStatus: item.status === "published" && item.moderation_status === "approved" && item.rights_status === "cleared" ? "VERIFIED" : "PENDING_VERIFICATION",
          };
        });
        if (active) { setItems(mapped); setState("ready"); }
      })
      .catch(() => { if (active && !controller.signal.aborted) { setItems([]); setState("unavailable"); } });
    return () => { active = false; controller.abort(); };
  }, []);

  return <><AiCinemaView userCredits={null} catalogItems={items} catalogState={state} productionMode /><AiCinemaPlaybackPanel titles={items.map(item => ({ id: item.id, title: item.title }))} /><AiCinemaCreatorWorkspace /></>;
}
