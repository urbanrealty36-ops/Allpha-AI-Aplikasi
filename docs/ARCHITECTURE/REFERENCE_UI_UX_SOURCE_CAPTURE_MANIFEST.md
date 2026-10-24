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
- Public assets under `public/assets/aistudio/`: 19; 11 exact-path copies exist in canonical `apps/web/public/`, 8 are missing at exact canonical path.
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
| `public/assets/aistudio/ALLPHA_UNIVERSE_MASTER_PRD_v3.0.0_COMPLETE__1__3ae29f78.md` | 129536 | `ff7b7b14b1245da0d6e6510dea4f033d8099c1a9` | missing at canonical path |
| `public/assets/aistudio/Screenshot_20261015-164747_fd4f48e4.jpg` | 915577 | `4a2dee71322ee123ff7a835789e0e5820af3fda2` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261020-224657_48336231.jpg` | 464766 | `53e9c361665384c8e66d9379468eeac5d18a0788` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg` | 1105749 | `808ddbb761676c06e91ba6e092244511e1d1e899` | missing at canonical path |
| `public/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg` | 699468 | `dc1dbd4d93a89155e44dc0d0e499b3022684aabc` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-174657_88e4a1c1.jpg` | 644676 | `d2383fd34b56cff879be3fd2291ab0662aae51e3` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg` | 590774 | `4182881e0a3d78e7d1a757e2c2622fea98d3a151` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg` | 672454 | `0730fcf3e580a6c8a3bc10cc6aabfb4cd1d45010` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-185525_22a42efd.jpg` | 1104144 | `8e58ed3ef6c1562c027ad45ff56f265e357e2d77` | missing at canonical path |
| `public/assets/aistudio/Screenshot_20261023-190053_0db052a1.jpg` | 586619 | `14e593bb3b4f465f386294f8250cf7c26ebf7d5d` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-191515_c07d41e9.jpg` | 558343 | `2844a29f29371611e638158eae79a167560eafd1` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-204929_f99e67e4.jpg` | 741976 | `b63fe9a95b0b1aceff9315731b0156ef53a2d161` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-205615_1e35e812.jpg` | 685285 | `597c4ee0de2cc0ab7e114ef650f2d4a18916812d` | present at same canonical path |
| `public/assets/aistudio/Screenshot_20261023-211448_393205d1.jpg` | 651621 | `422d339e4c9c48e2bac26c9bf435c93408fb58b3` | present at same canonical path |
| `public/assets/aistudio/file_000000000124820cac0b31096f36996d_47c73336.png` | 2284057 | `12d6c93d1f47e22017355db24d5c5f9d650eac64` | missing at canonical path |
| `public/assets/aistudio/file_00000000560c820baca9cd747fc97471_b104badb.png` | 2070206 | `b0cbd91174768e7eb979f9920b85f637f7d920f4` | missing at canonical path |
| `public/assets/aistudio/file_000000008064820b8790f095225931fd_64393eeb.png` | 2092646 | `e89cac55c852fc19a76c53427fe79ba42426ef50` | missing at canonical path |
| `public/assets/aistudio/file_00000000d1c08207a6952642d1a26363_df39e383.png` | 2674422 | `7bcb5eb6a77de90eb449a8acfda0ddf7aeadcb66` | missing at canonical path |
| `public/assets/aistudio/file_00000000d5a08211bff1d1706016eb9d_2018bbd5.png` | 2663435 | `749060b67cf8d143fc360c6c45e7742b849c27ab` | missing at canonical path |

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

The GitHub connector successfully exposes source tree metadata (path, byte size and Git blob SHA) and text files, but binary blob retrieval fails UTF-8 decoding and base64 fetch for binary files returns no content. The execution container also has no network DNS access to fetch raw GitHub binary assets. Therefore, missing binary files are explicitly inventoried and must not be claimed as copied. The available source evidence supports the file hashes/sizes above, not byte-for-byte transfer of the missing assets.

## Runtime isolation

- `apps/web/tsconfig.json` excludes `reference-source/**` and `components/reference-ui/*.tsx`; reference UI components are intentionally source snapshots until wired route-by-route.
- `docs/reference-ui-source/**` is outside `apps/web` and therefore outside the Next.js app directory.
- `.reference` files are source snapshots, not TS/TSX compilation units.
- No Railway build/deploy was run or requested. Vercel is the only deployment target, and no deployment is claimed by this inventory commit.

## Acceptance status

- Checkpoint A: source component/route/asset inventory documented; route gaps explicit.
- Checkpoint B: text/source capture is present, but binary capture is **incomplete** until the missing public assets are copied and hash-verified. Temporary AI Studio media remains inventory-only unless an actual UI reference is established.
- Component runtime wiring and full API integration are deliberately out of scope for A/B.
