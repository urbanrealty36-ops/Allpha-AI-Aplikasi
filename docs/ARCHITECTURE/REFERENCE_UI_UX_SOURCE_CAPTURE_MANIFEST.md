# Reference UI/UX Source Capture Manifest

**Observed:** 2026-10-24  
**Reference repository:** https://github.com/urbanrealty36-ops/Allpha-Front-End-UI-New  
**Reference branch/tree:** `main` / `aad317c1f651163f065cd42b9ae35267d18f354a` (current source head for the 2026-10-26 inventory)  
**Canonical repository:** https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi  
**Scope:** Checkpoints A/B source capture and asset path reconciliation only. This is an inventory, not a phase/status plan.

## Capture summary

- Source tree: 90 entries, 73 file blobs.
- Text/source/config files: 47; 47 confirmed present in the canonical reference archive or copied component target.
- Top-level React components: 25; source component files exist under `apps/web/components/reference-ui/`, and archived originals exist under `docs/reference-ui-source/Allpha-Front-End-UI-New/`.
- Public assets under `public/assets/aistudio/`: 20; all 20 exact-path copies exist in canonical `apps/web/public/` after byte-size, source Git blob SHA-1 and SHA-256 verification.
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
| `public/assets/aistudio/file_00000000e2f48207b9fbf70131d4041f_fb06dd70.png` | 2030869 | `ad78971cbe154e01325dc90f8ca0c88349c35c2b` | verified at `apps/web/public/assets/aistudio/file_00000000e2f48207b9fbf70131d4041f_fb06dd70.png`; bytes=2030869; Git blob SHA-1=ad78971cbe154e01325dc90f8ca0c88349c35c2b; SHA-256=fb06dd700425e620f8a26d28af76ae40f8da5a76b70aa7cb1bffb1e688899473 |

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
- Checkpoint B: text/source capture and all 20 public assets are present at exact canonical paths. The eight previously missing assets and the current-head addition were verified by expected byte size, source Git blob SHA-1 and recorded SHA-256. Temporary AI Studio media remains inventory-only unless an actual UI reference is established.
- Component runtime wiring and full API integration are deliberately out of scope for A/B.


## Exact component-copy verification

After the initial manifest was recorded, commit [`fb526a2`](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/commit/fb526a246dcced5970271086126ee94c8024716e) copied the 13 remaining divergent component files byte-for-byte from reference source. A subsequent Git tree comparison verified **25 of 25** top-level reference component files now have the same Git blob SHA at `apps/web/components/reference-ui/<component>` as at `components/<component>` in reference tree `5184f44e9f6c4e641cbe37e9f743583cf40d785e`.

This is source-copy evidence only. Component route wiring, production API behavior, and UI acceptance remain unverified. The latest current-head public asset is now present and checksum-verified; UI route wiring and acceptance remain separate gates.
