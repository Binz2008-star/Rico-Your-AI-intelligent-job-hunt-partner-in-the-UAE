import { RicoProfileResponseSchema, UploadCVResponseSchema } from "@/lib/schemas";

describe("Career Profile read-only contract", () => {
  it("accepts a profile response with a typed career_profile", () => {
    const raw = {
      profile_exists: true,
      email: "test@example.com",
      skills: ["Python"],
      career_profile: {
        skills: [{ name: "Python" }],
        certifications: [{ name: "PMP" }],
        languages: [{ name: "Arabic", proficiency: "Native" }],
      },
    };

    const parsed = RicoProfileResponseSchema.parse(raw);
    expect(parsed.career_profile).toBeDefined();
    expect(parsed.career_profile?.skills[0].name).toBe("Python");
    expect(parsed.career_profile?.certifications[0].name).toBe("PMP");
    expect(parsed.career_profile?.languages[0].name).toBe("Arabic");
  });

  it("allows career_profile to be null", () => {
    const raw = {
      profile_exists: true,
      email: "test@example.com",
      career_profile: null,
    };

    const parsed = RicoProfileResponseSchema.parse(raw);
    expect(parsed.career_profile).toBeNull();
  });

  it("rejects malformed career_profile item fields", () => {
    const raw = {
      profile_exists: true,
      career_profile: {
        skills: [{ name: "x".repeat(101) }],
      },
    };

    expect(() => RicoProfileResponseSchema.parse(raw)).toThrow();
  });

  it("rejects client-forged provenance in read career_profile", () => {
    const raw = {
      profile_exists: true,
      career_profile: {
        skills: [{ name: "Python", provenance: "client_forged" }],
      },
    };

    expect(() => RicoProfileResponseSchema.parse(raw)).toThrow();
  });
});

describe("Upload CV preview contract", () => {
  it("accepts typed work_experience and education", () => {
    const raw = {
      ok: true,
      status: "preview_ready",
      preview: {
        name: "Test",
        email: null,
        phone: null,
        current_role: null,
        experience_years: null,
        target_roles: [],
        skills_detected: [],
        existing_skills: [],
        skills: [],
        certifications: [],
        languages: [],
        work_experience: [
          { role: "Engineer", company: "Rico", provenance: "extracted_from_cv" },
        ],
        education: [
          { institution: "University", degree: "BSc", provenance: "extracted_from_cv" },
        ],
      },
    };

    const parsed = UploadCVResponseSchema.parse(raw);
    expect(parsed.preview?.work_experience?.[0].role).toBe("Engineer");
    expect(parsed.preview?.education?.[0].institution).toBe("University");
  });

  it("rejects oversized preview fields", () => {
    const raw = {
      ok: true,
      status: "preview_ready",
      preview: {
        name: "Test",
        email: null,
        phone: null,
        current_role: null,
        experience_years: null,
        target_roles: [],
        skills_detected: [],
        existing_skills: [],
        skills: [],
        certifications: [],
        languages: [],
        work_experience: [
          { role: "x".repeat(201), company: "Rico" },
        ],
        education: [],
      },
    };

    expect(() => UploadCVResponseSchema.parse(raw)).toThrow();
  });
});
