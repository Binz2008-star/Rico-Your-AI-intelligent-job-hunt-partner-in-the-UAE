// Workaround: Next.js's static tracer does not detect the @vercel/og font file
// (noto-sans-v27-latin-regular.ttf) because it's loaded via a dynamic
// `fs.readFileSync(fileURLToPath(join(import.meta.url, "../...ttf")))` call
// that can't be statically analyzed. As a result, the .nft.json trace for the
// opengraph-image route omits the font file, and OpenNext's copyTracedFiles
// step doesn't copy it to .open-next/server-functions/default/.
//
// This script runs after `next build` and:
//   1. Copies the missing @vercel/og files (font, wasm, edge.js) into the
//      standalone node_modules directory so copyTracedFiles can find them.
//   2. Adds the missing file paths to the standalone .nft.json trace so
//      copyTracedFiles knows to copy them.
//
// This is a Windows-specific workaround for a known @vercel/og + OpenNext
// tracing gap. On Linux the same gap may exist; the script is idempotent and
// safe on any platform.
import { readFileSync, writeFileSync, existsSync, copyFileSync, mkdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const webDir = join(__dirname, "..");
const nextDir = join(webDir, ".next");
const standaloneDir = join(nextDir, "standalone");
const standaloneNextDir = join(standaloneDir, ".next");
const standaloneServerDir = join(standaloneNextDir, "server");

// Source @vercel/og files in the real node_modules
const sourceOgDir = join(webDir, "node_modules", "next", "dist", "compiled", "@vercel", "og");
// Target @vercel/og in standalone node_modules
const standaloneOgDir = join(standaloneDir, "node_modules", "next", "dist", "compiled", "@vercel", "og");

// Files that @vercel/og needs at runtime but Next.js doesn't trace.
const missingFiles = [
  "noto-sans-v27-latin-regular.ttf",
  "index.edge.js",
  "resvg.wasm",
  "yoga.wasm",
];

// 1. Copy missing files to standalone node_modules
if (existsSync(standaloneOgDir)) {
  for (const file of missingFiles) {
    const src = join(sourceOgDir, file);
    const dst = join(standaloneOgDir, file);
    if (existsSync(src) && !existsSync(dst)) {
      copyFileSync(src, dst);
      console.log(`[patch-og-nft] Copied ${file} to standalone node_modules.`);
    }
  }
} else {
  console.log("[patch-og-nft] standalone @vercel/og dir not found, skipping file copy.");
}

// 2. Add missing file paths to the standalone .nft.json
const standaloneNftPath = join(standaloneServerDir, "app", "opengraph-image", "route.js.nft.json");
if (!existsSync(standaloneNftPath)) {
  console.log("[patch-og-nft] standalone opengraph-image .nft.json not found, skipping trace patch.");
  process.exit(0);
}

const nft = JSON.parse(readFileSync(standaloneNftPath, "utf8"));
// Paths in standalone .nft.json are relative to the route directory
const relPrefix = "../../../../node_modules/next/dist/compiled/@vercel/og/";
let added = 0;
for (const file of missingFiles) {
  const relPath = relPrefix + file;
  if (!nft.files.includes(relPath)) {
    nft.files.push(relPath);
    added++;
  }
}

if (added > 0) {
  writeFileSync(standaloneNftPath, JSON.stringify(nft, null, 2));
  console.log(`[patch-og-nft] Added ${added} missing @vercel/og file(s) to standalone trace.`);
} else {
  console.log("[patch-og-nft] All @vercel/og files already in standalone trace, no changes.");
}
