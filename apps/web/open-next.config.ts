import { defineCloudflareConfig } from "@opennextjs/cloudflare";
import kvIncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/kv-incremental-cache";

// OpenNext adapter configuration for Cloudflare Workers (0.6.x release line).
// Docs: https://opennext.js.org/cloudflare/former-releases/0.6/get-started
//
// 0.6.x is the last release line supporting Next.js 14. The 1.x line requires
// Next.js >=15.5.21. See PR description for the version constraint details.
//
// The KV incremental cache is wired here but stays inert until a
// `NEXT_INC_CACHE_KV` binding is uncommented in wrangler.jsonc. Until then
// OpenNext falls back to its default in-Worker cache.
export default defineCloudflareConfig({
  incrementalCache: kvIncrementalCache,
});
