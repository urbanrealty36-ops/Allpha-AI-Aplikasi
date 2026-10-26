"use client";

import Universe3DHubView from "../../../components/reference-ui/Universe3DHubView";

export default function Universe3DHubPage() {
  return (
    <Universe3DHubView
      onBackToFeed={() => window.location.assign("/feed")}
      userCredits={null}
      agentCredits={null}
      productionMode
    />
  );
}
