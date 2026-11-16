"use client";

import { useState } from "react";
import LiveExperienceStage, { type StageSlideItem } from "../../components/reference-ui/LiveExperienceStage";
import LiveStageAgentPrepPanel from "../../components/live/LiveStageAgentPrepPanel";

export default function LivePage() {
  const [revision, setRevision] = useState(0);
  const [stageTopic, setStageTopic] = useState<string | undefined>(undefined);
  const [stageSlides, setStageSlides] = useState<StageSlideItem[] | undefined>(undefined);

  function applyOutline(topic: string, slides: StageSlideItem[]) {
    setStageTopic(topic);
    setStageSlides(slides);
    setRevision(value => value + 1);
  }

  return (
    <>
      <LiveExperienceStage key={revision} onBackToFeed={() => { window.location.assign("/feed"); }} userCredits={null} agentCredits={null} liveStateAvailable={false} initialTopic={stageTopic} initialSlides={stageSlides} />
      <LiveStageAgentPrepPanel onApply={applyOutline} />
    </>
  );
}
