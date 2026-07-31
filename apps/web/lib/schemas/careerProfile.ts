import { z } from "zod";

export const ExperienceItemSchema = z.object({
  id: z.string().nullable().optional(),
  role: z.string().max(200).nullable().optional(),
  company: z.string().max(200).nullable().optional(),
  start_date: z.string().max(20).nullable().optional(),
  end_date: z.string().max(20).nullable().optional(),
  description: z.string().max(2000).nullable().optional(),
  location: z.string().max(200).nullable().optional(),
  provenance: z.literal("extracted_from_cv").optional(),
  source_document_id: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  confirmed_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
}).passthrough();

export const EducationItemSchema = z.object({
  id: z.string().nullable().optional(),
  institution: z.string().max(200).nullable().optional(),
  degree: z.string().max(100).nullable().optional(),
  field: z.string().max(100).nullable().optional(),
  start_date: z.string().max(20).nullable().optional(),
  end_date: z.string().max(20).nullable().optional(),
  provenance: z.literal("extracted_from_cv").optional(),
  source_document_id: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  confirmed_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
}).passthrough();

export const SkillItemSchema = z.object({
  name: z.string().max(100).nullable().optional(),
}).strict();

export const CertificationItemSchema = z.object({
  name: z.string().max(100).nullable().optional(),
}).strict();

export const LanguageItemSchema = z.object({
  name: z.string().max(100).nullable().optional(),
  proficiency: z.string().max(50).nullable().optional(),
}).strict();

export const CareerProfileSchema = z.object({
  skills: z.array(SkillItemSchema).optional().default([]),
  certifications: z.array(CertificationItemSchema).optional().default([]),
  languages: z.array(LanguageItemSchema).optional().default([]),
}).strict();

export type ExperienceItem = z.infer<typeof ExperienceItemSchema>;
export type EducationItem = z.infer<typeof EducationItemSchema>;
export type SkillItem = z.infer<typeof SkillItemSchema>;
export type CertificationItem = z.infer<typeof CertificationItemSchema>;
export type LanguageItem = z.infer<typeof LanguageItemSchema>;
export type CareerProfile = z.infer<typeof CareerProfileSchema>;
