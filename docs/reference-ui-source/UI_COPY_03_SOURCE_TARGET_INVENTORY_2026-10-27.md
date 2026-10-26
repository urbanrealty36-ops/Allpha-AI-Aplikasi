# UI-COPY-03 — Source/Target Inventory & Parity Report

Audit date: 2026-10-27
Reference: urbanrealty36-ops/Allpha-Front-End-UI-New, branch `main`, commit/tree `b6c9fc728d5d031a28b22fbbec9a546846900e87`
Canonical: urbanrealty36-ops/Allpha-AI-Aplikasi, branch `main`, tree `8e70685878371b12f53afc4b3ceab63887d14c27`
Master PRD: `docs/PRD/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE.md` (read in full; 3,690 lines, 195,048 characters; current file SHA `7a173b4f61654247ad98b8062c5a4f80d0266eb8`).
Operating contract: `AGENTS.md` (read before changes; SHA `aff5b0587fffcdad79cc06df9359f97be7217aed`).
Fixed phase plan: `docs/PHASES/ALLPHA_FIXED_PHASE_PLAN.md` (1,549 lines; SHA `e0f89de74da6fa450be960552ab961682c42c613`).

## Summary

Reference tree contains 120 tracked files. Target tree contains 720 tracked files. This mapping compares each reference path to its expected runtime location in `apps/web`; it is not a generic same-name search.

| Classification | Count | Meaning |
|---|---:|---|
| Identical | 54 | Mapped target has the same Git blob SHA as source |
| Changed | 29 | Mapped target exists but blob SHA differs; review required |
| Missing target | 15 | Expected mapped runtime file is absent |
| Needs mapping | 22 | Reference file is root/config/editor/temp artifact or needs an explicit destination decision |
| Source inventory total | 120 | All tracked reference files, including non-runtime/editor artifacts |

Important: identical SHA means byte-for-byte file identity only; it does not prove that the component is mounted by a production route or connected to canonical APIs. Conversely, changed files may contain necessary production adapters and must not be overwritten blindly.

## Changed mapped files

| Reference source | Source blob | Expected target | Target blob | Source bytes | Target bytes |
|---|---|---|---|---:|---:|
| `app/globals.css` | `5a7873abc0ed6501cce9c86073350bfc602cfcb2` | `apps/web/app/globals.css` | `1d22919ddf820336cbe4d17064ca7d97e367032b` | 49 | 21314 |
| `app/layout.tsx` | `c5be526c1af94f870460af9138f33254740f4213` | `apps/web/app/layout.tsx` | `5a408ddb84d5e1698bba513ce70f7186ff9e7af1` | 1492 | 1617 |
| `app/manifest.ts` | `52416276c182bf89094ff33815027857b5c313f1` | `apps/web/app/manifest.ts` | `7c58e6c16cfaea97056cb0dab6aa99c2921d3c58` | 711 | 583 |
| `app/page.tsx` | `0bddfa37d8dbc307d0362b742b66ee644f9dfba0` | `apps/web/app/page.tsx` | `92243cd55f314bb3223ff55ef616ac05dfb02630` | 27393 | 192 |
| `components/AgentGoalsTasksModal.tsx` | `8db6dbcde28b190b40308f546c4a6d200329caee` | `apps/web/components/reference-ui/AgentGoalsTasksModal.tsx` | `107bf62b0716ffa5ee557e743bb317b277e1f70b` | 29614 | 27183 |
| `components/AgentIdentityModal.tsx` | `8d70617d267921fd2fb47a1e8e23fc2239e1f1d2` | `apps/web/components/reference-ui/AgentIdentityModal.tsx` | `8946f917bce6143551e8f5f9fbd9d166703b0a6e` | 17826 | 17836 |
| `components/AgentPassportModal.tsx` | `492b28ada01526a73a45f7a079435f204e8fcd3f` | `apps/web/components/reference-ui/AgentPassportModal.tsx` | `1eeb6cfebd9f75a2d9d472e4ee522443bdbea1b8` | 15366 | 15376 |
| `components/AiCinemaView.tsx` | `b00d437932622e0d4651cc89ce386b4a1cdfb7fa` | `apps/web/components/reference-ui/AiCinemaView.tsx` | `232ecee2e029a6f96f6d23aa020043621fef7632` | 87141 | 88959 |
| `components/AllphaHubView.tsx` | `3fa129dede142534ef262c1fc740fee1a31df52b` | `apps/web/components/reference-ui/AllphaHubView.tsx` | `8c650ed9d5b8bd26c53622a4d6c74b24d5254255` | 92142 | 80959 |
| `components/AskAiView.tsx` | `d66753039df606195330ff2b5ba8793399d81d4c` | `apps/web/components/reference-ui/AskAiView.tsx` | `479a846417cf84ae29c36a03aef8dff7029fa149` | 12764 | 12199 |
| `components/AuthOnboardingFlow.tsx` | `30207dd3bfb7cf9864d5a142bb299f245c9adb46` | `apps/web/components/reference-ui/AuthOnboardingFlow.tsx` | `563d3aeada4383dd01d8237d49ba91f49eaa7466` | 41907 | 37235 |
| `components/AuthOnboardingPage.tsx` | `007e68a0503d1a67799b7bb87b39ae0fc28978b3` | `apps/web/components/reference-ui/AuthOnboardingPage.tsx` | `8b0895cde30009ed67599d9f270e3cab4deef499` | 56053 | 56386 |
| `components/BottomNav.tsx` | `c2841cf7048bd2130f8634435d683523e04325d6` | `apps/web/components/reference-ui/BottomNav.tsx` | `ee3f7840306068e7981fddc5fe626361b0ccbc34` | 6357 | 6276 |
| `components/CreatePostModal.tsx` | `e620b3ad820523050d47ce2f564e9bd269f6ab9a` | `apps/web/components/reference-ui/CreatePostModal.tsx` | `bfd9c95dabfd8c93d0792bc231ef8c863ee4d405` | 40441 | 26731 |
| `components/CreatorStudioModal.tsx` | `2daf53afeb094221d2f4a5eefb69e3fdfeb24a81` | `apps/web/components/reference-ui/CreatorStudioModal.tsx` | `18b964117f2c554461f1f08aa0f67ea2e4e10180` | 19487 | 19497 |
| `components/ExploreView.tsx` | `9e1f3a9f7c43ee4ed0c250842d6c93e0200e5701` | `apps/web/components/reference-ui/ExploreView.tsx` | `ac5d5610fb6bbd639bb912c3862db48148670696` | 45818 | 40373 |
| `components/FeedView.tsx` | `ac8710aa0fb9bd407640361b5c7d2c0fcb707869` | `apps/web/components/reference-ui/FeedView.tsx` | `c0548ff5115a9af72a18df66ee012a12396f574c` | 27457 | 32095 |
| `components/LiveExperienceStage.tsx` | `8787caa184b9a8161bcc287ea6ff27cfb75c8a3f` | `apps/web/components/reference-ui/LiveExperienceStage.tsx` | `78905bee6cca0021b1c43b757c12e4dad1490310` | 42376 | 21752 |
| `components/MarketplaceView.tsx` | `6859ccc63768b6f636d3622cecebc8edd5a5fa7c` | `apps/web/components/reference-ui/MarketplaceView.tsx` | `2ba33232d001ec17ed6a996bd541cd0dbf843fdc` | 40151 | 9602 |
| `components/MessagesView.tsx` | `20685f8eb9e5f16df8f1163bcd9198f23cc25f56` | `apps/web/components/reference-ui/MessagesView.tsx` | `7074ec42cf02c670781d353c02235a9317204a7e` | 8108 | 8050 |
| `components/Navbar.tsx` | `fab9a740d3a7a8d81e7219be27f01b9d67ca8261` | `apps/web/components/reference-ui/Navbar.tsx` | `1c7c20dfd654f7517ad283b21bdfd18af42877d1` | 7830 | 6993 |
| `components/ProfileView.tsx` | `c55452a78cee9f1e33f2480bea39049f24882348` | `apps/web/components/reference-ui/ProfileView.tsx` | `e405a7dc4a25e828e2067438ce446c0aa8bab7d1` | 75029 | 49422 |
| `components/ReelsView.tsx` | `f2e226a6a81e6ad0867525481e49d77b5d1001ee` | `apps/web/components/reference-ui/ReelsView.tsx` | `16a30fe8d9123498e651c056b036e28e73683620` | 21865 | 20854 |
| `components/StoreAndBoothModal.tsx` | `f8d26bc5123527faa355292c7a653310335ff3c4` | `apps/web/components/reference-ui/StoreAndBoothModal.tsx` | `9bfe689492abef50d2cbef70c145de3dbd9934a7` | 44490 | 44500 |
| `components/StoriesViewerModal.tsx` | `9743c5f28f6eeb38d744179ca31125c6cbccc499` | `apps/web/components/reference-ui/StoriesViewerModal.tsx` | `942f05fd3a9f878c87f8cdf15abaee9f6060ec6f` | 11588 | 11598 |
| `components/ThreeWorldView.tsx` | `33064372c878be0ede72340fa4d97e9ab253fe9b` | `apps/web/components/reference-ui/ThreeWorldView.tsx` | `74da25aa6790bc7a3d340423e08ddcd533e01f38` | 50284 | 49784 |
| `next.config.ts` | `d0dc5db8f2ad53184650d433c9b73ab5c8bf716a` | `apps/web/next.config.ts` | `038f361883ee53aefe825ee13bd17acac7d1796c` | 870 | 155 |
| `package.json` | `763670e6c124537245a7383244af2e657a8550a7` | `apps/web/package.json` | `760af032b9dd39387ddcea91aa5b6a7cb34ea4de` | 1084 | 1004 |
| `tsconfig.json` | `fd8d34e6573933aefe3c409017402eadab1b5d67` | `apps/web/tsconfig.json` | `d8f22dc9592576d5f1806108e18da4ed58ccc84a` | 658 | 731 |

## Missing mapped targets

| Reference source | Source blob | Expected target | Bytes |
|---|---|---|---:|
| `app/api/agent/interact/route.ts` | `ee906b48eab82c27af9f027ac0e86e8fe0dfc9d8` | `apps/web/app/api/agent/interact/route.ts` | 8437 |
| `app/not-found.tsx` | `92ae07505de3e593debf4bf81ddec45395d028ed` | `apps/web/app/not-found.tsx` | 628 |
| `lib/menggu3dEngine.ts` | `d77482123c22c17d078b35e434b5db17190b4c25` | `apps/web/lib/reference-ui/menggu3dEngine.ts` | 47156 |
| `lib/store.ts` | `f19b70fd0bde5226f1014c91ba80646d87d780a3` | `apps/web/lib/reference-ui/store.ts` | 42966 |
| `lib/utils.ts` | `bd0c391ddd1088e9067844c48835bf4abcd61783` | `apps/web/lib/reference-ui/utils.ts` | 166 |
| `metadata.json` | `bdf05d7ef886cfd6950950c2959cae7e75617a08` | `apps/web/metadata.json` | 329 |
| `src/assets/images/menggu_ai_plaza_1793024772235.jpg` | `e3453adbce9b27379c40ff1f4951ee99a812b4c9` | `apps/web/src/assets/images/menggu_ai_plaza_1793024772235.jpg` | 784618 |
| `src/assets/images/menggu_billboard_ads_1793024797427.jpg` | `0fc11cb48a923c8809e91ea020a140b69a650924` | `apps/web/src/assets/images/menggu_billboard_ads_1793024797427.jpg` | 858428 |
| `src/assets/images/menggu_district_spatial_1793024717088.jpg` | `ce20cae5341da20fdba8e78abcaa4af1b7f947a0` | `apps/web/src/assets/images/menggu_district_spatial_1793024717088.jpg` | 840740 |
| `src/assets/images/menggu_landmark_citadel_1793024745732.jpg` | `5ce4e268c6850b97332584a3e2eae2fb38707678` | `apps/web/src/assets/images/menggu_landmark_citadel_1793024745732.jpg` | 479671 |
| `src/assets/images/slide_cinema_3d_1793023017033.jpg` | `41215ecaa20ff755d23e4d4a55e9bcbfb8cf2786` | `apps/web/src/assets/images/slide_cinema_3d_1793023017033.jpg` | 933431 |
| `src/assets/images/slide_dualfeed_3d_1793022941224.jpg` | `64d55a937cbf6f003e541134f18701323a7c425e` | `apps/web/src/assets/images/slide_dualfeed_3d_1793022941224.jpg` | 678134 |
| `src/assets/images/slide_livestage_3d_1793023043430.jpg` | `b61f4b658d21defb9ad435763be99d8b9e2d9756` | `apps/web/src/assets/images/slide_livestage_3d_1793023043430.jpg` | 747019 |
| `src/assets/images/slide_welcome_3d_1793022854882.jpg` | `e5ee63bf3a746755cd84b3d5d7866627c160bea6` | `apps/web/src/assets/images/slide_welcome_3d_1793022854882.jpg` | 726956 |
| `src/assets/images/slide_worlds_3d_1793022976093.jpg` | `6c26a03ad657f19aa4fb9ad4941f1999066d10e5` | `apps/web/src/assets/images/slide_worlds_3d_1793022976093.jpg` | 926272 |

## Needs explicit mapping / disposition

| Reference path | Blob | Bytes | Required disposition |
|---|---|---:|---|
| `.aistudio/artifacts/brain/1d13ab21-817e-4d1f-a254-43aa07d213e4/.tempmediaStorage/media_1792927868515_27d9c3b6.jpg` | `597c4ee0de2cc0ab7e114ef650f2d4a18916812d` | 685285 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/1d13ab21-817e-4d1f-a254-43aa07d213e4/.tempmediaStorage/media_1792927877515_236bcb9a.jpg` | `422d339e4c9c48e2bac26c9bf435c93408fb58b3` | 651621 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/1d13ab21-817e-4d1f-a254-43aa07d213e4/.tempmediaStorage/media_1792927885600_95de86d1.jpg` | `4182881e0a3d78e7d1a757e2c2622fea98d3a151` | 590774 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/1d13ab21-817e-4d1f-a254-43aa07d213e4/.tempmediaStorage/media_1792927899892_f4040c6e.jpg` | `dc1dbd4d93a89155e44dc0d0e499b3022684aabc` | 699468 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792752503552_e609cdd7.jpg` | `d2383fd34b56cff879be3fd2291ab0662aae51e3` | 644676 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792755028276_a24e5eb7.jpg` | `4182881e0a3d78e7d1a757e2c2622fea98d3a151` | 590774 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792755048475_f3472b58.jpg` | `0730fcf3e580a6c8a3bc10cc6aabfb4cd1d45010` | 672454 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792758232833_e2b17fc4.jpg` | `14e593bb3b4f465f386294f8250cf7c26ebf7d5d` | 586619 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792758261098_0af534ee.jpg` | `2844a29f29371611e638158eae79a167560eafd1` | 558343 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792758287565_7ffa1b2b.jpg` | `8e58ed3ef6c1562c027ad45ff56f265e357e2d77` | 1104144 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/4967876d-dfb4-4705-8237-92690eb09d3f/.tempmediaStorage/media_1792914845743_56c70907.png` | `ad78971cbe154e01325dc90f8ca0c88349c35c2b` | 2030869 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/6d67fdf5-e3ca-4a7a-8764-67cc4b060325/.tempmediaStorage/media_1793018578414_32fc5366.jpg` | `2ea569299feed8e955c0387d6e09e0d691485271` | 497481 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/6d67fdf5-e3ca-4a7a-8764-67cc4b060325/.tempmediaStorage/media_1793023752807_02e665cc.jpg` | `23e8cf6bb32a62dac3503454c79baa8435f44454` | 538903 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/b7c56f9d-546d-4107-956d-26f1948eec14/.tempmediaStorage/media_1792763439888_4853ca49.jpg` | `b63fe9a95b0b1aceff9315731b0156ef53a2d161` | 741976 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.aistudio/artifacts/brain/b7c56f9d-546d-4107-956d-26f1948eec14/.tempmediaStorage/media_1792764131790_87fa76a7.jpg` | `597c4ee0de2cc0ab7e114ef650f2d4a18916812d` | 685285 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.env.example` | `b718d75a509a12ec1dff4ddbaad7eff91071a3c6` | 59 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.eslintrc.json` | `15b1ed91acf662a241dac0425b14ae0837d81f5d` | 24 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `.gitignore` | `71b810ccacbcc72d38715bfb7dd8822b7ff013d2` | 67 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `eslint.config.mjs` | `3e9def882f86c18e294dee5f8c06a74f510cf8dd` | 314 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `next-env.d.ts` | `830fb594ca2970a827555c28a253b097367e08d8` | 262 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `postcss.config.mjs` | `e2167ce22cc33cf23e33d17f03dc9bcc783d7ff6` | 168 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |
| `tsconfig.tsbuildinfo` | `b8fd0aa43fdbb8f7bd1e47b426164aca71f79ebf` | 213688 | Decide whether runtime config, archival-only, duplicate asset, editor artifact, generated file, or intentionally excluded. |

## Safety and synchronization rules

1. Preserve source layout/classes/tokens/typography/button/card/modal/container behavior; no redesign or lookalike replacement.
2. Keep canonical Next.js PWA routes, Supabase Auth and FastAPI API contracts. Do not replace canonical route orchestration with the reference demo app/store.
3. Never carry reference fixture balances, fake purchases, simulated payment receipts, hardcoded analytics/royalties/views, fabricated credit bonuses, fake AI-generation success, or local-only message delivery into production.
4. For each changed runtime component, perform content-level diff and categorize edits as visual/layout, type/import, route integration, API adapter, safety/data fixture, or obsolete code before merging. Prefer retaining source markup/classes and changing only data wiring/handlers where required.
5. For missing targets, copy only after reviewing imports/dependencies and canonical architecture. Do not copy reference `package.json`, `next.config.ts`, `tsconfig.json`, `app/layout.tsx`, `app/page.tsx`, `app/manifest.ts`, or `app/globals.css` wholesale into the monorepo; reconcile configuration with the existing app.
6. Reference assets under `public/` should be SHA-checked against target assets. `src/assets/images/*` duplicates may be intentionally served from `public/assets/*`; document alias/mapping rather than needlessly duplicating large binaries. Editor/temp media under `.aistudio/*` is not automatically a production asset.
7. The reference snapshot archive and manifest are evidence of source preservation, not complete runtime parity. Phase remains `UI-COPY-03 IN_PROGRESS` until every source item has a disposition, every requested runtime UI is mapped, styling/code drift is accounted for, and required source/CI evidence is recorded.
8. Per Product Owner instruction, no staging, real-world checkout, or physical-device test is performed in this pass. Build/typecheck/viewport behavior must not be claimed verified without actual evidence.

## First-priority follow-up

- Reconcile the changed visual source files, beginning with onboarding/auth, Creator Studio, Profile, Marketplace, Live Experience, Store & Booth, AI Cinema, Explore, Feed, Reels, Messages, Navbar, and 3D renderer/engine.
- Review all 15 missing targets, especially `lib/menggu3dEngine.ts` and source `lib/store.ts`: the 3D engine needs a deliberate port; the reference store is demo state and must not replace canonical production data.
- Add a source-to-runtime route map for all pages/modals, then verify that CSS classes/tokens and assets used by the mounted routes are preserved.
