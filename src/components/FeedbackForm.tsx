"use client";

import { FormEvent, useRef, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { siteConfig } from "@/config/site";
import { companyTypes, conversationOptions, usefulnessOptions, validateFeedback } from "@/lib/feedback-schema";

export function FeedbackForm() {
  const [status, setStatus] = useState<"idle" | "sending" | "success" | "error">("idle");
  const [invalid, setInvalid] = useState(false);
  const inFlight = useRef(false);
  const attempt = useRef<{ payload: string; id: string } | null>(null);
  const feedbackMailto = `mailto:${siteConfig.email}?subject=${encodeURIComponent(`Workflow feedback for ${siteConfig.companyName}`)}`;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    const form = event.currentTarget;
    const input = Object.fromEntries(new FormData(form).entries());
    const fields = validateFeedback(input);
    if (!fields) { setInvalid(true); setStatus("error"); return; }
    setInvalid(false);
    inFlight.current = true;
    setStatus("sending");
    try {
      const payload = JSON.stringify(fields);
      // Preserve the ID on retries with unchanged answers after an uncertain response.
      if (attempt.current?.payload !== payload) attempt.current = { payload, id: crypto.randomUUID() };
      const submissionId = attempt.current.id;
      const response = await fetch("/api/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...fields, website: "", submissionId }),
        signal: AbortSignal.timeout(25_000),
      });
      const receipt = await response.json();
      if (!response.ok || receipt?.ok !== true || receipt?.submissionId !== submissionId) throw new Error("Not accepted");
      form.reset();
      attempt.current = null;
      setStatus("success");
    } catch { setStatus("error"); }
    finally { inFlight.current = false; }
  }

  return <form className="feedbackForm" aria-label={`Share your workflow with ${siteConfig.companyName}`} onSubmit={submit} aria-busy={status === "sending"}>
    <div className="form-honeypot" aria-hidden="true"><label>Leave this field empty<input name="website" type="text" tabIndex={-1} autoComplete="off"/></label></div>
    <div className="formGrid">
      {[
        { label: "Name", name: "name", type: "text", autoComplete: "name", maxLength: 120 },
        { label: "Work Email", name: "email", type: "email", autoComplete: "email", maxLength: 254 },
        { label: "Company", name: "company", type: "text", autoComplete: "organization", maxLength: 160 },
        { label: "Role", name: "role", type: "text", autoComplete: "organization-title", maxLength: 120 },
      ].map(({ label, ...props }) => <label key={props.name}>{label}<input {...props} required disabled={status === "sending"}/></label>)}
      <label>Company Type<select name="company_type" required defaultValue="" disabled={status === "sending"}><option value="" disabled>Select one</option>{companyTypes.map(option => <option key={option}>{option}</option>)}</select></label>
      <label>Phone / WhatsApp <span>OPTIONAL</span><input name="phone" type="tel" autoComplete="tel" maxLength={50} disabled={status === "sending"}/></label>
    </div>
    <Question n="01" name="current_process" text="How does your team currently create electrical or MEP layouts from architectural drawings?" disabled={status === "sending"}/>
    <Question n="02" name="time_sink" text="Which part of that process takes the most engineering time?" disabled={status === "sending"}/>
    <fieldset disabled={status === "sending"}><legend><span>03</span>Would an automatically generated first-draft electrical layout be useful?</legend><div className="radioRow">{usefulnessOptions.map(option => <label key={option}><input type="radio" name="usefulness" value={option} required/><span>{option}</span></label>)}</div></fieldset>
    <Question n="04" name="barriers" text="What would prevent your team from using a system like this?" disabled={status === "sending"}/>
    <fieldset disabled={status === "sending"}><legend><span>05</span>Would you be open to a 15-minute conversation?</legend><div className="radioRow short">{conversationOptions.map(option => <label key={option}><input type="radio" name="conversation" value={option} required/><span>{option}</span></label>)}</div></fieldset>
    <div className="formSubmit">
      <button className="button primary" type="submit" disabled={status === "sending"}>{status === "sending" ? "Sending..." : "Share feedback"}<ArrowUpRight/></button>
      <div aria-live="polite" aria-atomic="true">
        {status === "success" && <p className="form-success">Thanks — your response has been received.</p>}
        {status === "error" && <p className="form-error">{invalid && <>Please complete all required fields with a valid email address. </>}We couldn&apos;t submit your response. Please try again or email us at <a href={feedbackMailto}>{siteConfig.email}</a>.</p>}
      </div>
      <p>Your responses are used only for product research and follow-up.</p>
    </div>
  </form>;
}

function Question({ n, name, text, disabled }: { n: string; name: string; text: string; disabled: boolean }) {
  return <label className="question"><span>{n}</span>{text}<textarea name={name} rows={4} maxLength={2000} required disabled={disabled}/></label>;
}
