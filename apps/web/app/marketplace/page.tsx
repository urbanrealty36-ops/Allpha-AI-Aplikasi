"use client";

import MarketplaceView from "../../components/reference-ui/MarketplaceView";

/**
 * Reference-faithful Marketplace screen.
 * The canonical listing API and Booth/Tenant join are not yet available, so
 * this route deliberately renders the source layout with an empty catalog.
 * No demo listings, credits, likes, purchase callback, or fake success.
 */
export default function MarketplacePage() {
  return (
    <MarketplaceView
      items={[]}
      userCredits={null}
      catalogState="unavailable"
      onBuyItem={() => {
        // Fail closed until the canonical purchase contract is implemented.
      }}
    />
  );
}
