# Reference UI source snapshot

- Source repository: https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New.git
- Source branch: main
- Source tree SHA: 5184f44e9f6c4e641cbe37e9f743583cf40d785e
- Snapshot purpose: preserve reference frontend code/layout/components before the next integration pass.
- Import mode: source files are stored with the `.reference` suffix so they do not alter the canonical app's build or styling at this snapshot stage.
- No component is claimed integrated merely because its source is present here.

## Preserved source files

- `app/page.tsx`
- `app/globals.css`
- `app/layout.tsx`
- `app/manifest.ts`
- `app/not-found.tsx`
- `app/api/agent/interact/route.ts`
- `components/AgentGoalsTasksModal.tsx`
- `components/AgentIdentityModal.tsx`
- `components/AiCinemaView.tsx`
- `components/AllphaHubView.tsx`
- `components/AskAiModal.tsx`
- `components/AskAiView.tsx`
- `components/AuthOnboardingFlow.tsx`
- `components/BottomNav.tsx`
- `components/CreatePostModal.tsx`
- `components/ExploreView.tsx`
- `components/FeedView.tsx`
- `components/GenerateModal.tsx`
- `components/LiveExperienceStage.tsx`
- `components/MarketplaceView.tsx`
- `components/MessagesView.tsx`
- `components/Navbar.tsx`
- `components/PostDetailView.tsx`
- `components/ProfileView.tsx`
- `components/ReelsView.tsx`
- `components/SkillsChallengeHub.tsx`
- `components/TakeoverControlView.tsx`
- `components/TakeoverModal.tsx`
- `components/ThreeWorldView.tsx`
- `components/Universe3DExperience.tsx`
- `components/Universe3DHubView.tsx`
- `hooks/use-mobile.ts`
- `hooks/usePWAInstall.ts`
- `lib/store.ts`
- `lib/utils.ts`
- `package.json`
- `tsconfig.json`
- `next.config.ts`
- `postcss.config.mjs`
- `metadata.json`
- `eslint.config.mjs`
- `.eslintrc.json`
- `.env.example`

## Important separation

This is a source snapshot, not the completed UI/UX refactor. The next implementation pass must port the unchanged visual components/layout into canonical routes and adapt data/event boundaries without redesigning the reference UI. Any local sample data in the reference must not be treated as canonical business data.
