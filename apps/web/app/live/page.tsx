"use client";

import LiveExperienceStage from "../../components/reference-ui/LiveExperienceStage";

/** Source-faithful Live Stage shell. Runtime data and media actions remain disabled until a canonical Live session is returned by FastAPI. */
export default function LivePage() {
  return <LiveExperienceStage onBackToFeed={() => { window.location.assign("/feed"); }} userCredits={0} agentCredits={0} liveStateAvailable={false} />;
}
