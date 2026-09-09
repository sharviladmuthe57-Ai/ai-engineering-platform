import { submissionIdPattern, validateFeedback } from "./feedback-schema.ts";

type Config = { webhookUrl?: string; webhookSecret?: string };
const MAX_BODY_BYTES = 24_000;
const reply = (status: number, body: object) => Response.json(body, {
  status, headers: { "Cache-Control": "no-store" },
});

// Tests inject transport; the public route uses server environment values and real fetch.
export async function handleFeedback(request: Request, config: Config, send: typeof fetch = fetch) {
  if (request.method !== "POST") return reply(405, { ok: false, code: "METHOD_NOT_ALLOWED" });
  const origin = request.headers.get("origin");
  if ((origin && origin !== new URL(request.url).origin) || request.headers.get("sec-fetch-site") === "cross-site") {
    return reply(403, { ok: false, code: "INVALID_ORIGIN" });
  }
  if (request.headers.get("content-type")?.split(";")[0].trim() !== "application/json") {
    return reply(415, { ok: false, code: "JSON_REQUIRED" });
  }
  if (Number(request.headers.get("content-length")) > MAX_BODY_BYTES) return reply(413, { ok: false, code: "TOO_LARGE" });
  let input: Record<string, unknown>;
  try {
    // Bound the body even when Content-Length is absent or inaccurate.
    const reader = request.body?.getReader();
    if (!reader) return reply(400, { ok: false, code: "INVALID_FIELDS" });
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY_BYTES) {
        await reader.cancel();
        return reply(413, { ok: false, code: "TOO_LARGE" });
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    input = JSON.parse(new TextDecoder().decode(bytes));
  } catch { return reply(400, { ok: false, code: "INVALID_JSON" }); }
  const fields = validateFeedback(input);
  if (!fields || typeof input.submissionId !== "string" || !submissionIdPattern.test(input.submissionId)) {
    return reply(400, { ok: false, code: "INVALID_FIELDS" });
  }
  const webhookUrl = config.webhookUrl?.trim();
  const webhookSecret = config.webhookSecret?.trim();
  if (!webhookUrl || !webhookSecret || webhookSecret.length < 32 || !/^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/.test(webhookUrl)) {
    return reply(503, { ok: false, code: "FORM_NOT_CONFIGURED" });
  }
  try {
    const upstream = await send(webhookUrl, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret: webhookSecret, submissionId: input.submissionId, fields, source_page: "/#feedback" }),
      redirect: "follow", cache: "no-store", signal: AbortSignal.timeout(15_000),
    });
    if (!upstream.ok) return reply(502, { ok: false, code: "STORAGE_UNAVAILABLE" });
    const receipt = await upstream.json();
    if (receipt?.ok !== true || receipt?.submissionId !== input.submissionId) return reply(502, { ok: false, code: "STORAGE_REJECTED" });
    return reply(200, { ok: true, submissionId: input.submissionId });
  } catch {
    // Never log personal information, credentials, or the private webhook URL.
    return reply(502, { ok: false, code: "STORAGE_UNAVAILABLE" });
  }
}
