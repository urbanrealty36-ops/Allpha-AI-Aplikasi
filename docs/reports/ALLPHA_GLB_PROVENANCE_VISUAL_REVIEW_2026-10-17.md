# Allpha GLB Provenance & Visual Triage — 2026-10-17

## Scope and decision

This report records an evidence pass over the 927 physical GLB files reconciled from acquisition run [38908521488](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/38908521488) and repackaging run [39002086145](https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi/actions/runs/39002086145).

**No asset is approved. No Supabase upload or publication was performed.** This is a provenance/technical triage, not final visual or device acceptance.

## Acquisition and structural evidence

- 927 physical files; 927 unique SHA-256 hashes.
- 927/927 file sizes and SHA-256 values match the acquisition manifest.
- 927/927 GLB 2.0 containers passed header/chunk/JSON checks.
- Independent JSON inventory parsed 927/927 files.
- 2,993 meshes; approximately 9,502,619 vertices from POSITION accessors.
- 2,072 material declarations, 1,704 texture declarations, 1,639 image declarations.
- 0 external image URIs found in GLB JSON. This does not guarantee material/texture rendering fidelity.

## License/provenance disposition

| Source repository | Files | Repository evidence | Disposition |
|---|---:|---|---|
| [rostock/3DModels](https://github.com/rostock/3DModels) | 665 | Repository declares CC0-1.0 | Hold for per-asset provenance and visual review |
| [c-frame/valid-avatars-glb](https://github.com/c-frame/valid-avatars-glb) | 232 | Repository declares MIT | Hold for upstream VALID model provenance, likeness and redistribution review |
| [SpectraStudios/SourceCityToolkit_glb](https://github.com/SpectraStudios/SourceCityToolkit_glb) | 13 | CC0 with explicit Textures.com texture exceptions | Hold until per-file texture provenance is resolved |
| [ramjigeddam/3d](https://github.com/ramjigeddam/3d) | 17 | No verified license evidence in acquisition manifest | **Quarantine** pending rights evidence |

A repository-level license declaration is not automatic proof of rights to every embedded mesh, texture, logo, likeness or third-party contribution. Accordingly, all 927 files remain NOT_APPROVED.

## Category disposition

The acquisition category field is a filename/path heuristic only. 666 assets remain unmapped; the remaining values are candidates, not accepted product categories. Do not promote a category to the canonical asset manifest until human visual review ties the actual model to an Allpha product need.

## Visual and runtime QA status

- Geometry silhouette contact sheet: sample triage only; it does not faithfully render PBR materials or textures.
- Full per-asset visual acceptance: NOT RUN.
- Browser renderer test: NOT RUN.
- Real Android device test: NOT RUN.
- Real iOS device test: NOT RUN.
- Orientation/world scale acceptance: NOT RUN.
- Error/retry behavior, load time, frame rate and memory telemetry: NOT RUN.

## Required next gates

1. Keep 17 unknown-license assets quarantined.
2. Review upstream/likeness rights for 232 avatar models.
3. Identify and clear any restricted Textures.com/third-party textures for 13 Source City models.
4. Review each candidate visually in the browser and on Android/iOS, recording material/texture fidelity, orientation/scale, errors/retries, load time and memory.
5. Map category only from the actual visual evidence and Allpha product requirements.
6. Submit a separate approval packet for assets that pass all gates. Do not upload or publish automatically.

## Evidence bundle

The downloadable companion bundle includes the per-asset review matrix, acquisition manifest/reconciliation, summary JSON, source errors, and a sample geometry silhouette sheet. It is generated as an analysis artifact and is not itself a production asset registry.
