import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import type { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

/**
 * Registers the Three.js-bundled Meshopt decoder before GLTFLoader parses a
 * document that declares EXT_meshopt_compression. The decoder is shared by
 * previews and scene rendering so those paths cannot drift independently.
 */
export function configureAllphaGLTFLoader(loader: GLTFLoader): void {
  loader.setMeshoptDecoder(MeshoptDecoder);
}
