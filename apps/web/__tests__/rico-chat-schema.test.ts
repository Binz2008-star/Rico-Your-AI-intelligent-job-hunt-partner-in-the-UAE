import { describe, expect, it } from "vitest";

import { RicoChatResponseSchema } from "@/lib/schemas";

describe("RicoChatResponseSchema", () => {
  it("accepts the production public chat response shape", () => {
    const result = RicoChatResponseSchema.safeParse({
      message:
        "Welcome to Rico AI. Upload your CV or tell me your target role, UAE city preferences, and salary expectations.",
      type: "onboarding",
      matches: [],
      options: [],
      next_action: null,
      next_actions: [],
      intent: null,
      response_source: "keyword",
      provider: null,
      provider_state: null,
      reasons: [],
      role: null,
      success: true,
      error_ref: null,
      trace_id: "ERR-83D937A1",
      response: null,
      openai_available: true,
      deepseek_available: true,
      hf_available: true,
      provider_available: true,
      openai_model: "deepseek-v4-flash",
      profile_context_present: false,
      jotform_form_id: "261277622782059",
      debug_id: "361d9f64be81",
    });

    expect(result.success).toBe(true);
  });

  it("normalizes legacy primitive values used in chat options and matches", () => {
    const result = RicoChatResponseSchema.parse({
      message: 123,
      matches: [
        {
          title: 456,
          company: true,
          actions: ["save", 1, false, null],
          match_reasons: [1, "skill fit"],
        },
      ],
      options: [{ action: 99, label: false }],
      next_actions: null,
      reasons: [1, "ok"],
    });

    expect(result.message).toBe("123");
    expect(result.matches?.[0]?.title).toBe("456");
    expect(result.matches?.[0]?.company).toBe("true");
    expect(result.matches?.[0]?.actions).toEqual(["save", "1", "false"]);
    expect(result.options?.[0]?.action).toBe("99");
    expect(result.options?.[0]?.label).toBe("false");
    expect(result.next_actions).toBeUndefined();
    expect(result.reasons).toEqual(["1", "ok"]);
  });
});
