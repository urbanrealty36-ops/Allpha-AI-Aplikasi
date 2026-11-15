# External Repository Audit — Live Stage, AI Voice and 3D Character Adapters

**Date:** 2026-11-16  
**Target:** Allpha Universe · `urbanrealty36-ops/Allpha-AI-Aplikasi` · branch `main`  
**Scope:** Read-only source, dependency, license and architecture review of the three explicitly named repositories.  
**Decision boundary:** Allpha keeps its own FastAPI, Agent Runtime, Model Router, Workflow Engine, Memory/Knowledge and Supabase source of truth. This audit does not authorize importing an external runtime or selecting a Live media provider.

## Executive decision

| Repository | Pinned main commit | License evidence | Allpha disposition |
|---|---|---|---|
| [GetStream/Vision-Agents](https://github.com/GetStream/Vision-Agents/tree/8e2d3a1990244db5c303e1f969af3a3a85b12440) | `8e2d3a1990244db5c303e1f969af3a3a85b12440` | Apache-2.0 root LICENSE | Selective real-time audio/video processor and turn-detection adapter candidate; do not import its full Agent runtime |
| [moeru-ai/airi](https://github.com/moeru-ai/airi/tree/62a01b28725903e41c1feccc9e790c21dc7e04f4) | `62a01b28725903e41c1feccc9e790c21dc7e04f4` | MIT root LICENSE; inspected packages declare MIT | Selective avatar/character/VRM/lip-sync/audio/motion source candidate; port to Allpha React/Three.js architecture |
| [langzizhixin/LangQing](https://github.com/langzizhixin/LangQing/tree/7a7e961609add712df5923246e8796a5fb4d1d9d) | `7a7e961609add712df5923246e8796a5fb4d1d9d` | No LICENSE file found in inspected repository tree; LICENSE fetch returns 404 | Research-only; do not copy, package, deploy or depend on it |

No external source files or package dependencies were imported into Allpha during this audit.

## 1. Vision Agents — real-time voice/video/vision and turn-taking

**Evidence inspected:** pinned repository README, root LICENSE and `agents-core/pyproject.toml`.

The README describes a Python framework for real-time multimodal agents: WebRTC media, video processors (YOLO/Roboflow/custom PyTorch/ONNX), VAD/diarization/turn detection, provider integrations for STT/TTS/LLM, tool calling/MCP, phone integrations and a built-in HTTP/metrics/deployment layer. It also documents its own `Agent(edge=..., agent_user=..., instructions=..., llm=..., processors=...)` composition.

The inspected core package requires Python >=3.10 and directly depends on:
- `getstream[webrtc,telemetry]>=4.1,<5`
- `aiortc>=1.14,<1.15`, `av>=14.2,<17`
- `mcp>=1.23.3,<2`, FastAPI, Uvicorn, ONNX Runtime, NumPy, Pillow and other runtime utilities.
- Optional provider extras include OpenAI, Gemini, ElevenLabs, Deepgram, Cartesia, NVIDIA, Roboflow, Ultralytics, AWS, Qdrant/TurboPuffer and others.

**Fit:** good technical reference for media event handling, processor lifecycle, VAD/turn-taking, audio/video timing and adapter boundaries. It may accelerate a future Allpha real-time media adapter after Live architecture approval.

**Boundary/risk:** it is more than a media codec library. It brings its own Agent/LLM orchestration, edge abstraction, HTTP server, telemetry, MCP, RAG and memory integrations; README describes cross-session memory through Stream Chat. Importing the whole runtime would duplicate Allpha's canonical Agent Runtime, Model Router, Workflow/Tool policy and Memory/Knowledge ownership. Its core dependency set also includes Stream's SDK and WebRTC implementation even though the README says other edge networks can be used.

**Recommendation:** do not add `vision-agents` as a second runtime or mount its server as a second API. If approved later, extract/port only the required processor and turn-detection contracts behind an Allpha-owned Live Session/Agent Runtime adapter. FastAPI must continue to authorize session, participant roles, tool permissions, budgets and audit. The SFU/TURN provider decision remains separate; Vision Agents is not itself approval of a Live media provider.

## 2. AIRI — avatar, character, renderer, audio and animation

**Evidence inspected:** pinned root README/LICENSE and package manifests for `stage-ui-three`, `stage-ui-live2d`, `core-character`, `model-driver-lipsync`, `motion-driver-magic`, `pipelines-audio` and `apps/stage-web`.

The inspected source has concrete modules for:
- Three.js/VRM character rendering and VRM animation via `@pixiv/three-vrm` and `@pixiv/three-vrm-animation`.
- Live2D rendering and model parameter/expression/motion APIs.
- Character contracts/runtime orchestration.
- Lip-sync drivers and audio capture/VAD/encode/stream pipelines.
- Motion generation/animation driver abstractions.

**License:** root repository is MIT; inspected `stage-ui-three`, `stage-ui-live2d`, `core-character`, `motion-driver-magic`, `pipelines-audio` and `apps/stage-web` package manifests declare MIT. Preserve required copyright/license notices for any adapted code. Individual sample avatars, VRM/Live2D models, textures, voice assets and other third-party assets require separate provenance/license checks; the repository license does not automatically clear those assets.

**Compatibility:** AIRI's Stage Web is Vue/Vite with Pinia and TresJS (`@tresjs/core`, `@tresjs/cientos`) over Three.js. The relevant packages are marked `private: true` and use workspace dependencies such as `@proj-airi/stream-kit`. They are not drop-in React packages for Allpha's Next.js/React and React Three Fiber surfaces.

**Recommendation:** use AIRI as a source/reference for character state contracts, VRM loading/expressions, lip-sync timing and motion-driver algorithms. Port selected logic into Allpha's React/Three.js renderer with typed Allpha Agent identity/asset manifests. Do not add the private Vue workspace packages directly to Allpha's dependency graph and do not adopt AIRI's inference/provider/runtime stack as a second Agent Runtime.

## 3. LangQing — digital human candidate

**Evidence inspected:** pinned README, `main.py`, `config.json`, `requirements.txt` and repository tree.

The README claims real-time 2D/2.5D/3D digital humans, WebRTC, low latency, high-resolution output, lip-sync, gestures, ASR/TTS, multi-agent integration, RAG and workflow orchestration. Those are README claims, not verified capabilities.

The source snapshot does not substantiate the claims:
- `main.py` is 461 bytes and contains imports only; no visible application routes, media pipeline, model invocation or runtime implementation was present in that file.
- `requirements.txt` and `config.json` are each one byte (newline only); no usable dependency lock/manifest was present in the inspected paths.
- The repository tree is very small (21 entries in the inspected recursive tree) and does not expose a complete implementation corresponding to the README claims.
- No LICENSE file was found in the inspected tree; fetching `LICENSE` returns 404. No production API contract or complete documented integration surface was established.

**Recommendation:** research/reference only. Do not copy source, install it as a dependency, deploy it, or derive performance/capacity assumptions from its README. Reconsider only after the owner supplies a complete source snapshot, explicit license/rights, dependency lock, API contracts, deployment instructions and reproducible evidence.

## Allpha integration decision and next boundary

1. Keep the canonical Allpha Agent Runtime, Model Router, Workflow Engine, Memory/Knowledge ACL, FastAPI and Supabase ownership unchanged.
2. Keep the Live media provider decision open under [ADR-WP10-001](../ADR/ADR-WP10-001-live-media-provider-and-session-transport.md). No SFU, TURN, recording or provider credential is selected by this audit.
3. Before importing any Vision Agents/AIRI code, create a source-to-module mapping, pin exact commits, inventory copied files and transitive dependencies, reconcile licenses/notices/SBOM, and define an Allpha-owned adapter contract.
4. No LangQing code is eligible for import until license and source completeness blockers are resolved.

**Audit limitation:** this is a repository/source snapshot audit, not a live provider benchmark, security certification, performance test, device test or license opinion. No external project was executed.
