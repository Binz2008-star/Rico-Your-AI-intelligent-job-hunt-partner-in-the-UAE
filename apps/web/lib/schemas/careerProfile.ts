import { z } from "zod";

export const ProvenanceStateSchema = z.enum([
  "extracted_from_cv",
  "confirmed_by_user",
  "edited_by_user",
  "added_by_user",
  "suggested_by_rico",
  "needs_confirmation",
]);

export const BaseCareerItemSchema = z.object({
  id: z.string().optional(),
  source_document_id: z.string().nullable().optional(),
  provenance: ProvenanceStateSchema.default("added_by_user"),
  confidence: z.number().min(0).max(1).nullable().optional(),
  confirmed_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});

export const ExperienceItemSchema = BaseCareerItemSchema.extend({
  role: z.string().nullable().optional(),
  company: z.string().nullable().optional(),
  start_date: z.string().nullable().optional(),
  end_date: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  location: z.string().nullable().optional(),
}).passthrough();

export const EducationItemSchema = BaseCareerItemSchema.extend({
  institution: z.string().nullable().optional(),
  degree: z.string().nullable().optional(),
  field: z.string().nullable().optional(),
  start_date: z.string().nullable().optional(),
  end_date: z.string().nullable().optional(),
}).passthrough();

export const CertificationItemSchema = BaseCareerItemSchema.extend({
  name: z.string().nullable().optional(),
  issuer: z.string().nullable().optional(),
  date: z.string().nullable().optional(),
}).passthrough();

export const LanguageItemSchema = BaseCareerItemSchema.extend({
  name: z.string().nullable().optional(),
  proficiency: z.string().nullable().optional(),
}).passthrough();

export const SkillItemSchema = BaseCareerItemSchema.extend({
  name: z.string().nullable().optional(),
}).passthrough();

export const CareerProfileSchema = z.object({
  summary: z.string().nullable().optional(),
  experience: z.array(ExperienceItemSchema).default([]),
  education: z.array(EducationItemSchema).default([]),
  certifications: z.array(CertificationItemSchema).default([]),
  languages: z.array(LanguageItemSchema).default([]),
  skills: z.array(SkillItemSchema).default([]),
});

export const CompletenessBreakdownItemSchema = z.object({
  section: z.string(),
  score: z.number().min(0).max(1),
  missing: z.array(z.string()).default([]),
  needs_confirmation: z.boolean().default(false),
});

export const CompletenessSchema = z.object({
  score: z.number().min(0).max(1),
  sections: z.array(CompletenessBreakdownItemSchema).default([]),
});

export type ProvenanceState = z.infer<typeof ProvenanceStateSchema>;
export type ExperienceItem = z.infer<typeof ExperienceItemSchema>;
export type EducationItem = z.infer<typeof EducationItemSchema>;
export type CertificationItem = z.infer<typeof CertificationItemSchema>;
export type LanguageItem = z.infer<typeof LanguageItemSchema>;
export type SkillItem = z.infer<typeof SkillItemSchema>;
export type CareerProfile = z.infer<typeof CareerProfileSchema>;
export type CompletenessBreakdownItem = z.infer<typeof CompletenessBreakdownItemSchema>;
export type Completeness = z.infer<typeof CompletenessSchema>;
