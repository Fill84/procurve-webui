#!/usr/bin/env node
/**
 * Regenerate `src/routeTree.gen.ts` from the files under `src/routes/`.
 *
 * The Vite plugin (`TanStackRouterVite`) normally regenerates the route
 * tree on dev-server start and build, but `tsc -b` runs BEFORE `vite
 * build` in our npm `build` script and needs the generated file to
 * type-check. Running this script first guarantees the generated file
 * is fresh whenever we type-check.
 */
import { Generator, getConfig } from "@tanstack/router-generator";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");

const config = getConfig({}, root);
const generator = new Generator({ config, root });
await generator.run();
console.log("[gen-routes] routeTree.gen.ts regenerated");
