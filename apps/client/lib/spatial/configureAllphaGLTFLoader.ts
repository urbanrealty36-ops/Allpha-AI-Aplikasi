import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import type { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

/**
 * Registers the Three.js-bundled Meshopt decoder before GLTFLoader parses a
 * document that declares EXT_meshopt_compression. Keep the native adapter
 * local to the Expo app so Metro resolves the decoder inside its project root.
 */
export function configureAllphaGLTFLoader(loader: GLTFLoader): void {
  loader.setMeshoptDecoder(MeshoptDecoder);
}
