import { z } from "zod";

/** Sample-only disclaimer used everywhere seeded jobs surface. */
export const SAMPLE_JOBS_DISCLAIMER =
  "sample UAE matches — not live jobs";

export const seedJobSchema = z.object({
  id: z.string(),
  role: z.string(),
  company: z.string(),
  city: z.string(),
  salary: z.string(),
  posted: z.string(),
  score: z.number(),
  why: z.array(z.string()),
  gaps: z.array(z.string()).optional(),
  tags: z.array(z.string()),
});
export type SeedJobSchema = z.infer<typeof seedJobSchema>;

/* ---------- Chat turns (server input) ---------- */

export const ricoTurnSchema = z.object({
  role: z.enum(["user", "assistant"]),
  text: z.string(),
});
export type RicoTurn = z.infer<typeof ricoTurnSchema>;

export const ricoChatInputSchema = z.object({
  messages: z.array(ricoTurnSchema),
});
export type RicoChatInput = z.infer<typeof ricoChatInputSchema>;

/* ---------- Server reply ---------- */

export const ricoReplySchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("text"), text: z.string() }),
  z.object({
    kind: z.literal("jobs"),
    text: z.string(),
    source: z.literal("seed"),
    disclaimer: z.literal(SAMPLE_JOBS_DISCLAIMER),
    jobs: z.array(seedJobSchema),
  }),
  z.object({
    kind: z.literal("no_match"),
    text: z.string(),
    query: z.string(),
  }),
  z.object({
    kind: z.literal("error"),
    text: z.string(),
    code: z.number().optional(),
  }),
]);
export type RicoReply = z.infer<typeof ricoReplySchema>;

/* ---------- search_jobs tool contract ---------- */

export const searchJobsInputSchema = z.object({
  query: z.string().min(1),
  limit: z.number().int().positive().max(10).optional(),
});
export type SearchJobsInput = z.infer<typeof searchJobsInputSchema>;

export const searchJobsOutputSchema = z.object({
  source: z.literal("seed"),
  disclaimer: z.literal(SAMPLE_JOBS_DISCLAIMER),
  query: z.string(),
  jobs: z.array(seedJobSchema),
});
export type SearchJobsOutput = z.infer<typeof searchJobsOutputSchema>;

/* ---------- Client-side persisted entries (localStorage) ---------- */

export const liveEntrySchema = z.union([
  z.object({ role: z.literal("user"), text: z.string() }),
  z.object({
    role: z.literal("assistant"),
    kind: z.literal("text"),
    text: z.string(),
  }),
  z.object({
    role: z.literal("assistant"),
    kind: z.literal("jobs"),
    text: z.string(),
    jobs: z.array(seedJobSchema),
  }),
  z.object({
    role: z.literal("assistant"),
    kind: z.literal("no_match"),
    text: z.string(),
  }),
  z.object({
    role: z.literal("assistant"),
    kind: z.literal("error"),
    text: z.string(),
    canRetry: z.boolean().optional(),
  }),
  z.object({
    role: z.literal("assistant"),
    kind: z.literal("stopped"),
    text: z.string(),
  }),
]);
export type LiveEntry = z.infer<typeof liveEntrySchema>;

export const liveHistorySchema = z.array(liveEntrySchema);
