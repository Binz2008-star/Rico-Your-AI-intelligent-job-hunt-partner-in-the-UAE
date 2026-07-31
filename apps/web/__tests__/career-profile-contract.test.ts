import { describe, expect, it } from "vitest";
import { RicoProfileResponseSchema } from "@/lib/schemas";
import { CareerProfileUpdateSchema } from "@/lib/schemas/careerProfile";

describe("career profile Zod contract", () => {
  it("accepts a profile response with null career_profile and completeness", () => {
    const result = RicoProfileResponseSchema.safeParse({
      profile_exists: true,
      email: "test@example.com",
      career_profile: null,
      completeness: null,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.career_profile).toBeNull();
      expect(result.data.completeness).toBeNull();
    }
  });

  it("rejects provenance in a CareerProfileUpdate payload", () => {
    const result = CareerProfileUpdateSchema.safeParse({
      experience: [{ role: "CEO", provenance: "added_by_user" }],
    });
    expect(result.success).toBe(false);
  });

  it("rejects source_document_id in a CareerProfileUpdate payload", () => {
    const result = CareerProfileUpdateSchema.safeParse({
      experience: [{ role: "CEO", source_document_id: "doc-1" }],
    });
    expect(result.success).toBe(false);
  });

  it("rejects confidence in a CareerProfileUpdate payload", () => {
    const result = CareerProfileUpdateSchema.safeParse({
      experience: [{ role: "CEO", confidence: 0.95 }],
    });
    expect(result.success).toBe(false);
  });

  it("rejects confirmed_at in a CareerProfileUpdate payload", () => {
    const result = CareerProfileUpdateSchema.safeParse({
      experience: [{ role: "CEO", confirmed_at: "2024-01-01T00:00:00Z" }],
    });
    expect(result.success).toBe(false);
  });

  it("rejects updated_at in a CareerProfileUpdate payload", () => {
    const result = CareerProfileUpdateSchema.safeParse({
      experience: [{ role: "CEO", updated_at: "2024-01-01T00:00:00Z" }],
    });
    expect(result.success).toBe(false);
  });
});
