"use client";

import AiCinemaView from "../../components/reference-ui/AiCinemaView";

/**
 * Source-faithful AI Cinema screen. The reference catalog contains sample
 * films, fabricated ratings/views and local publish/approval/billing flows.
 * Until canonical Cinema, media, moderation and billing contracts exist,
 * this route intentionally provides no catalog data and fails closed.
 */
export default function AiCinemaPage() {
  return (
    <AiCinemaView
      userCredits={null}
      catalogItems={[]}
      catalogState="unavailable"
    />
  );
}
