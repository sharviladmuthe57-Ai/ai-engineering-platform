import { handleFeedback } from "@/lib/feedback-handler";

export const runtime = "nodejs";

export async function POST(request: Request) {
  return handleFeedback(request, {
    webhookUrl: process.env.GOOGLE_SHEETS_WEBHOOK_URL,
    webhookSecret: process.env.GOOGLE_SHEETS_WEBHOOK_SECRET,
  });
}
