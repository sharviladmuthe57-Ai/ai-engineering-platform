export const companyTypes = ["Electrical Contractor", "MEP Consultancy", "Engineering Consultancy", "Construction Company", "Architecture Firm", "BIM Team", "Building Automation", "Other"] as const;
export const usefulnessOptions = ["Very useful", "Possibly useful", "Depends", "Not useful"] as const;
export const conversationOptions = ["Yes", "No"] as const;

const fieldLimits = {
  name: 120, email: 254, company: 160, role: 120, company_type: 80,
  phone: 50, current_process: 2000, time_sink: 2000, usefulness: 40,
  barriers: 2000, conversation: 3,
} as const;
export type FeedbackFields = Record<keyof typeof fieldLimits, string>;
export const submissionIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function validateFeedback(input: unknown): FeedbackFields | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const record = input as Record<string, unknown>;
  if (typeof record.website !== "string" || record.website.trim()) return null;
  const fields = {} as FeedbackFields;
  for (const [key, limit] of Object.entries(fieldLimits)) {
    const value = record[key];
    if (typeof value !== "string") return null;
    const trimmed = value.trim();
    if (trimmed.length > limit || (key !== "phone" && !trimmed)) return null;
    if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(trimmed)) return null;
    fields[key as keyof FeedbackFields] = trimmed;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) return null;
  if (!(companyTypes as readonly string[]).includes(fields.company_type)) return null;
  if (!(usefulnessOptions as readonly string[]).includes(fields.usefulness)) return null;
  if (!(conversationOptions as readonly string[]).includes(fields.conversation)) return null;
  return fields;
}
