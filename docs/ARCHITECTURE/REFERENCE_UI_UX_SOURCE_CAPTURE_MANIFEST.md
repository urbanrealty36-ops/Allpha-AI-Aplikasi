# Reference UI/UX Source Capture Manifest

**Observed:** 2026-10-24  
**Reference repository:** https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New  
**Reference branch/tree:** `main` / `5184f44e9f6c4e641cbe37e9f743583cf40d785e`  
**Canonical repository:** https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi  
**Scope:** Checkpoints A/B source capture and asset path reconciliation only. This is an inventory, not a phase/status plan.

## Capture summary

- Source tree: 90 entries, 73 file blobs.
- Text/source/config files: 47; 47 confirmed present in the canonical reference archive or copied component target.
- Top-level React components: 25; source component files exist under `apps/web/components/reference-ui/`, and archived originals exist under `docs/reference-ui-source/Allpha-Front-End-UI-New/`.
- Public assets under `public/assets/aistudio/`: 19; all 19 exact-path copies exist in canonical `apps/web/public/` after binary capture and checksum verification.
- Temporary `.aistudio/artifacts/brain/**/.tempmediaStorage/*`: 8; inventoried but not copied to public runtime because no confirmed usage/path mapping.
- No backend/API/DB/Supabase or business-state changes were performed for this capture.

## Source files not to wire as runtime business logic

- `app/page.tsx` and `lib/store.ts`: reference UI orchestrator and local/sample state. Preserve as source-only; do not overwrite the canonical app root or treat initial/demo records as production data.
- `app/api/agent/interact/route.ts`: reference route only. Canonical business logic remains in `apps/api`.
- `package.json`, `next.config.ts`, `tsconfig.json`, `eslint.config.mjs`, `.eslintrc.json`, `postcss.config.mjs`, `next-env.d.ts`, `metadata.json`, `.env.example`: source snapshots only; do not replace canonical monorepo configuration or copy secrets.
- `hooks/use-mobile.ts`, `hooks/usePWAInstall.ts`, `lib/utils.ts`: captured source; runtime use remains pending component import/dependency reconciliation.

## Public asset reconciliation

| Source path | Bytes | Source blob SHA | Canonical target path |
|---|---:|---|---|
| `public/assets/aistudio/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE__1__3ae29f78.md` | 129536 | `ff7b7b14b1245da0d6e6510dea4f033d8099c1a9` | verified at `apps/web/public/assets/aistudio/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE__1__3ae29f78.md`; bytes=129536; Git blob SHA-1=ff7b7b14b1245da0d6e6510dea4f033d8099c1a9; SHA-256=3ae29f7817d501992da387da10147fdd48e95571f82d29ad16ac908744fd5b0b |
| `public/assets/aistudio/Screenshot_20261015-164747_fd4f48e4.jpg` | 915577 | `4a2dee71322ee123ff7a835789e0e5820af3fda2` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261020-224657_48336231.jpg` | 464766 | `53e9c361665384c8e66d9379468eeac5d18a0788` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg` | 1105749 | `808ddbb761676c06e91ba6e092244511e1d1e899` | verified at `apps/web/public/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg`; bytes=1105749; Git blob SHA-1=808ddbb761676c06e91ba6e092244511e1d1e899; SHA-256=2d568e437f45a2e7e5d1db00eb432e06c96ac90d99b0f5522f62248907a92f9e |
| `public/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg` | 699468 | `dc1dbd4d93a89155e44dc0d0e499b3022684aabc` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-174657_88e4a1c1.jpg` | 644676 | `d2383fd34b56cff879be3fd2291ab0662aae51e3` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg` | 590774 | `4182881e0a3d78e7d1a757e2c2622fea98d3a151` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg` | 672454 | `0730fcf3e580a6c8a3bc10cc6aabfb4cd1d45010` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-185525_22a42efd.jpg` | 1104144 | `8e58ed3ef6c1562c027ad45ff56f265e357e2d77` | verified at `apps/web/public/assets/aistudio/Screenshot_20261023-185525_22a42efd.jpg`; bytes=1104144; Git blob SHA-1=8e58ed3ef6c1562c027ad45ff56f265e357e2d77; SHA-256=22a42efd5b8a2fd65c528abbbf701004ffb97998f2dd1cd79a7ce5eb6f384317 |
| `public/assets/aistudio/Screenshot_20261023-190053_0db052a1.jpg` | 586619 | `14e593bb3b4f465f386294f8250cf7c26ebf7d5d` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-191515_c07d41e9.jpg` | 558343 | `2844a29f29371611e638158eae79a167560eafd1` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-204929_f99e67e4.jpg` | 741976 | `b63fe9a95b0b1aceff9315731b0156ef53a2d161` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-205615_1e35e812.jpg` | 685285 | `597c4ee0de2cc0ab7e114ef650f2d4a18916812d` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-211448_393205d1.jpg` | 651621 | `422d339e4c9c48e2bac26c9bf435c93408fb58b3` | present at same canonical path |
| `public/assets/aistudio/file_000000000124820cac0b31096f36996d_47c73336.png` | 2284057 | `12d6c93d1f47e22017355db24d5c5f9d650eac64` | verified at `apps/web/public/assets/aistudio/file_000000000124820cac0b31096f36996d_47c73336.png`; bytes=2284057; Git blob SHA-1=12d6c93d1f47e22017355db24d5c5f9d650eac64; SHA-256=47c7333642d6d3c598e0a42d1c8a334bd628130d1929d63ab9909ef953299a74 |
| `public/assets/aistudio/file_00000000560c820baca9cd747fc97471_b104badb.png` | 2070206 | `b0cbd91174768e7eb979f9920b85f637f7d920f4` | verified at `apps/web/public/assets/aistudio/file_00000000560c820baca9cd747fc97471_b104badb.png`; bytes=2070206; Git blob SHA-1=b0cbd91174768e7eb979f9920b85f637f7d920f4; SHA-256=b104badbde9698f5fa6f700793822b829445f59d02e71c5097d323896eb1142a |
| `public/assets/aistudio/file_000000008064820b8790f095225931fd_64393eeb.png` | 2092646 | `e89cac55c852fc19a76c53427fe79ba42426ef50` | verified at `apps/web/public/assets/aistudio/file_000000008064820b8790f095225931fd_64393eeb.png`; bytes=2092646; Git blob SHA-1=e89cac55c852fc19a76c53427fe79ba42426ef50; SHA-256=64393eebe03c4d992101688c9d0158043e83a6de3567480b93d9b31f8fe849ee |
| `public/assets/aistudio/file_00000000d1c08207a6952642d1a26363_df39e383.png` | 2674422 | `7bcb5eb6a77de90eb449a8acfda0ddf7aeadcb66` | verified at `apps/web/public/assets/aistudio/file_00000000d1c08207a6952642d1a26363_df39e383.png`; bytes=2674422; Git blob SHA-1=7bcb5eb6a77de90eb449a8acfda0ddf7aeadcb66; SHA-256=df39e38360f889314b856793f4ff1fc190f9f88791e307ce78c7c45a1b2d2841 |
| `public/assets/aistudio/file_00000000d5a08211bff1d1706016eb9d_2018bbd5.png` | 2663435 | `749060b67cf8d143fc360c6c45e7742b849c27ab` | verified at `apps/web/public/assets/aistudio/file_00000000d5a08211bff1d1706016eb9d_2018bbd5.png`; bytes=2663435; Git blob SHA-1=749060b67cf8d143fc360c6c45e7742b849c27ab; SHA-256=2018bbd59ebb4750ae9b77f0d6ad383eac8cc8dd42d4feec1364d6436465ccc5 |

## Temporary AI Studio media inventory

These files exist in the source Git tree, but are not in `public/` and have no confirmed component references. Preserve the inventory; do not automatically publish these temporary files.

| Source path | Bytes | Source blob SHA | Disposition |
|---|---:|---|---|
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792752503552_e609cdd7.jpg` | 644676 | `d2383fd34b56cff879be3fd2291ab0662aae51e3` | not copied; temporary source media, no confirmed UI runtime reference |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792755028276_a24e5eb7.jpg` | 590774 | `4182881e0a3d78e7d1a757e2c2622fea98d3a151` | not copied; temporary source media, no confirmed UI runtime reference |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792755048475_f3472b58.jpg` | 672454 | `0730fcf3e580a6c8a3bc10cc6aabfb4cd1d45010` | not copied; temporary source media, no confirmed UI runtime reference |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792758232833_e2b17fc4.jpg` | 586619 | `14e593bb3b4f465f386294f8250cf7c26ebf7d5d` | not copied; temporary source media, no confirmed UI runtime reference |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792758261098_0af534ee.jpg` | 558343 | `2844a29f29371611e638158eae79a167560eafd1` | not copied; temporary source media, no confirmed UI runtime reference |
| `.aistudio/artifacts/brain/3c911de3-54df-47f7-a52a-41a1abbf6242/.tempmediaStorage/media_1792758287565_7ffa1b2b.jpg` | 1104144 | `8e58ed3ef6c1562c027ad45ff56f265e357e2d77` | not copied; temporary source media, no confirmed UI runtime reference |
| `.aistudio/artifacts/brain/b7c56f9d-546d-4107-956d-26f1948eec14/.tempmediaStorage/media_1792763439888_4853ca49.jpg` | 741976 | `b63fe9a95b0b1aceff9315731b0156ef53a2d161` | not copied; temporary source media, no confirmed UI runtime reference |
| `.aistudio/artifacts/brain/b7c56f9d-546d-4107-956d-26f1948eec14/.tempmediaStorage/media_1792764131790_87fa76a7.jpg` | 685285 | `597c4ee0de2cc0ab7e114ef650f2d4a18916812d` | not copied; temporary source media, no confirmed UI runtime reference |

## Transfer limitation encountered

Historical limitation (resolved by the verified capture workflow): direct connector binary decoding was unavailable, so the eight assets are fetched by GitHub Actions from the pinned source commit. The workflow refuses to commit if any byte size or source Git blob SHA-1 differs, then records SHA-256 for each target file in this manifest.

## Runtime isolation

- `apps/web/tsconfig.json` excludes `reference-source/**` and `components/reference-ui/*.tsx`; reference UI components are intentionally source snapshots until wired route-by-route.
- `docs/reference-ui-source/**` is outside `apps/web` and therefore outside the Next.js app directory.
- `.reference` files are source snapshots, not TS/TSX compilation units.
- No Railway build/deploy was run or requested. Vercel is the only deployment target, and no deployment is claimed by this inventory commit.

## Acceptance status

- Checkpoint A: source component/route/asset inventory documented; route gaps explicit.
- Checkpoint B: text/source capture and all 19 public assets are present at exact canonical paths. The eight previously missing assets were copied from the pinned reference source commit and verified by expected byte size, source Git blob SHA-1, and recorded SHA-256. Temporary AI Studio media remains inventory-only unless an actual UI reference is established.
- Component runtime wiring and full API integration are deliberately out of scope for A/B.


## Exact component-copy verification

After the initial manifest was recorded, commit [`fb526a2`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/fb526a246dcced5970271086126ee94c8024716e) copied the 13 remaining divergent component files byte-for-byte from reference source. A subsequent Git tree comparison verified **25 of 25** top-level reference component files now have the same Git blob SHA at `apps/web/components/reference-ui/<component>` as at `components/<component>` in reference tree `5184f44e9f6c4e641cbe37e9f743583cf40d785e`.

This is source-copy evidence only. Component route wiring, production API behavior, and UI acceptance remain unverified. Binary asset transfer remains incomplete as stated above.


## Source sync update — 2026-10-27 (reference main b6c9fc728d5d031a28b22fbbec9a546846900e87)

The reference repository advanced after the original capture recorded above. Latest observed source HEAD: `b6c9fc728d5d031a28b22fbbec9a546846900e87` ([commit](https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New/commit/b6c9fc728d5d031a28b22fbbec9a546846900e87)). Nine UI components not present as named files in the canonical target's `apps/web/components/reference-ui/` at the audited target HEAD were archived byte-for-byte as source snapshots under `docs/reference-ui-source/` and have now also been copied into the canonical runtime reference component folder. Their visual/source code is preserved; only `@/lib/store` imports were redirected to the existing `@/lib/reference-store`. They are not yet mounted by production routes: several contain local/demo state and must be wired to canonical FastAPI contracts before live use.

| Reference source | Source blob SHA | UTF-8 bytes | Canonical archive |
|---|---|---:|---|
| `components/AgentPassportModal.tsx` | `492b28ada01526a73a45f7a079435f204e8fcd3f` | 15366 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__AgentPassportModal_tsx.reference` |
| `components/AuthOnboardingPage.tsx` | `007e68a0503d1a67799b7bb87b39ae0fc28978b3` | 56053 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__AuthOnboardingPage_tsx.reference` |
| `components/CreatorStudioModal.tsx` | `2daf53afeb094221d2f4a5eefb69e3fdfeb24a81` | 19487 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__CreatorStudioModal_tsx.reference` |
| `components/Menggu3DUniverseGallery.tsx` | `28ab5f90acbc71fd06a02390b8390005bfe362ee` | 58945 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__Menggu3DUniverseGallery_tsx.reference` |
| `components/Menggu3DViewerModal.tsx` | `5a2b8ddfb1aa266ed65f65a368ef7326ed85e63b` | 18783 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__Menggu3DViewerModal_tsx.reference` |
| `components/NotificationsModal.tsx` | `c6044b8544d06307ec3239a203d187fb6c522e63` | 8719 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__NotificationsModal_tsx.reference` |
| `components/StoriesViewerModal.tsx` | `9743c5f28f6eeb38d744179ca31125c6cbccc499` | 11588 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__StoriesViewerModal_tsx.reference` |
| `components/StoreAndBoothModal.tsx` | `f8d26bc5123527faa355292c7a653310335ff3c4` | 44490 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__StoreAndBoothModal_tsx.reference` |
| `components/ThemeCatalogModal.tsx` | `be599258062337a5bf966c3a9d48ec3284fb0b69` | 7111 | `docs/reference-ui-source/Allpha-Front-End-UI-New/components__ThemeCatalogModal_tsx.reference` |

The reference repository has updated Menggu3D images and additional October 26 screenshots, but its current Git tree contains zero `.glb` files. The canonical application Git tree also contains zero `.glb` files. Thus the claimed 927 GLBs are not evidenced as committed files in either audited tree; they must be inventoried from the actual configured Storage/catalog before a registration or publication count is asserted. This source sync does not change any Phase acceptance status.


## Runtime source-copy update — 2026-10-27

Direct-to-`main` commit [285be07](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/285be070fc8862481be66492129ab9742f3a70b6) copied the nine missing current reference components into `apps/web/components/reference-ui/` and the 3D engine into `apps/web/lib/menggu3dEngine.ts`. Visual component bodies were copied from source HEAD `b6c9fc728d5d031a28b22fbbec9a546846900e87`; only the local store import specifier was adapted to the canonical existing `reference-store.ts` where required. No route was switched to these components, no business state was changed, and no backend/DB/Storage state was mutated. The next step remains compile/typecheck/build and source-to-route reconciliation; do not treat copied-but-unmounted components as production feature acceptance.


### Additional current reference assets — Menggu3D

Pinned to reference `main` commit `b6c9fc728d5d031a28b22fbbec9a546846900e87`; the five source images are required by the copied 3D gallery/viewer presentation.

| Source path | Bytes | Source blob SHA | Canonical target path |
|---|---:|---|---|
| `public/assets/menggu3d/ai_plaza.jpg` | 784618 | `e3453adbce9b27379c40ff1f4951ee99a812b4c9` | verified at `apps/web/public/assets/menggu3d/ai_plaza.jpg`; bytes=784618; Git blob SHA-1=e3453adbce9b27379c40ff1f4951ee99a812b4c9; SHA-256=13e8fb3a8d2b2737c847955ed12e12c645a79578a58565cfd427db4c68046573 |
| `public/assets/menggu3d/billboard_ads.jpg` | 858428 | `0fc11cb48a923c8809e91ea020a140b69a650924` | verified at `apps/web/public/assets/menggu3d/billboard_ads.jpg`; bytes=858428; Git blob SHA-1=0fc11cb48a923c8809e91ea020a140b69a650924; SHA-256=ab219a41135782d9500163e7811d8e7d3e940a8104f8f8c53ec8ef5965d09f66 |
| `public/assets/menggu3d/booth_3d.jpg` | 926272 | `6c26a03ad657f19aa4fb9ad4941f1999066d10e5` | verified at `apps/web/public/assets/menggu3d/booth_3d.jpg`; bytes=926272; Git blob SHA-1=6c26a03ad657f19aa4fb9ad4941f1999066d10e5; SHA-256=5f0e7ae05e2a7895c0e489bb1f1268f8946c228c8c5d899552860c1d69741fa6 |
| `public/assets/menggu3d/district_spatial.jpg` | 840740 | `ce20cae5341da20fdba8e78abcaa4af1b7f947a0` | verified at `apps/web/public/assets/menggu3d/district_spatial.jpg`; bytes=840740; Git blob SHA-1=ce20cae5341da20fdba8e78abcaa4af1b7f947a0; SHA-256=5de1df9d43cea707279479a23d743ec08ceb2f50c570b45cb1e61d6fa6043d73 |
| `public/assets/menggu3d/landmark_citadel.jpg` | 479671 | `5ce4e268c6850b97332584a3e2eae2fb38707678` | verified at `apps/web/public/assets/menggu3d/landmark_citadel.jpg`; bytes=479671; Git blob SHA-1=5ce4e268c6850b97332584a3e2eae2fb38707678; SHA-256=a894475e4730e87faa59848a2713df9f9a9c70bce1e401e3895ec8c9cdf8eff1 |
