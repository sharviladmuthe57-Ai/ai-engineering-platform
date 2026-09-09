# Kairo Labs: receive website responses in Google Sheets

## Current status

The website integration and exact Apps Script are implemented. No Google Sheet
or Google deployment has been created by this task, and no live response has
been saved yet. Until the two server environment values are configured, the form
returns an error and keeps the visitor's answers. It never claims success.

Use your ordinary Google account. Do not create a paid Google Cloud project,
enable billing, buy storage, or add an API key. Apps Script quotas can stop
requests; the website treats that as a failure, not as a reason to upgrade.

## One-time Google setup

Work through these steps one at a time. You can ask for help at any step.

1. Open [Google Sheets](https://sheets.google.com) using your Google account.
   Create a blank spreadsheet and name it **Kairo Labs Leads**. Keep its sharing
   **Restricted**; visitors must not be able to read your leads.
2. In that spreadsheet, choose **Extensions → Apps Script**. Name the script
   **Kairo Labs Leads**. Replace the example code with the entire contents of
   [scripts/google-apps-script.gs](../scripts/google-apps-script.gs) and save.
3. At the top, select the function **setup**, then choose **Run**. Review Google's
   permission request yourself. The script needs to edit your spreadsheet. If
   Google blocks it or you are unsure about a permission, stop and ask for help;
   do not bypass browser security warnings. Successful setup creates a
   **Responses** tab and its column headings without deleting existing tabs.
4. In Apps Script choose **Project Settings** (gear) → **Script properties**.
   `SPREADSHEET_ID` and `WEBHOOK_SECRET` should now exist. Copy the value of
   `WEBHOOK_SECRET` for the website's private environment setting below.
   Do not put it in GitHub, public code, the spreadsheet, or a chat message.
5. Choose **Deploy → New deployment**, then the gear/type selector → **Web app**.
   Set **Execute as: Me** and **Who has access: Anyone**. Review and approve this
   yourself. Only the submission endpoint is public; the sheet stays private.
   The endpoint requires the private shared secret before it can append a row.
6. Choose **Deploy** and copy the **Web app URL** ending in `/exec`. Do not use
   the test URL ending in `/dev`. Keep that URL in private configuration too.

## Connect the website on Netlify Free

The user authorized Netlify Free instead of Vercel. Do not upgrade, enable
auto-recharge, add a card, buy a domain, or enable paid integrations.

1. In Netlify open the Kairo Labs project → **Project configuration → Environment
   variables** (some accounts label this **Site configuration**).
2. Add these two environment variables for the production deployment. If scopes
   are offered, they must include **Functions**; use secret values where offered.

   | Key | Value |
   | --- | --- |
   | `GOOGLE_SHEETS_WEBHOOK_URL` | Your Google Web app `/exec` URL |
   | `GOOGLE_SHEETS_WEBHOOK_SECRET` | The `WEBHOOK_SECRET` value from Script properties |

   Neither key may have a `NEXT_PUBLIC_` prefix. Do not paste them into
   `netlify.toml` or any source file.
3. Open **Deploys → Trigger deploy → Deploy project** to apply the settings.
   Stay on the **Free** plan. If Free credits are exhausted, wait for their reset;
   do not buy credits. See [Netlify Free deployment](netlify-free-deployment.md).

For local development only, copy `.env.example` to `.env.local`, supply the same
two values, and restart the website server. `.env.local` is ignored by Git.

## Where you see names, emails, companies and answers

Open **Kairo Labs Leads → Responses** in Google Sheets on your phone or laptop.
There is one row per accepted submission. The columns, in order, are:

1. Timestamp (Google server time; displayed using the spreadsheet's time zone)
2. Name
3. Work Email
4. Company
5. Role
6. Company Type
7. Current Workflow
8. Biggest Time Sink
9. First-Draft Electrical Usefulness
10. Biggest Blocker
11. Open to 15-Minute Conversation
12. Phone / WhatsApp (optional)
13. Source Page (`/#feedback`; no tracking parameters, IP address or browser data)
14. Submission ID (a random identifier used to avoid duplicate retry rows)

Do not reorder or rename the header row: the script refuses submissions if the
headings do not match, to prevent writing answers into the wrong columns.
The header stays frozen. Adjust display widths and the timestamp's number format
in Sheets if desired. No passwords or payment details are collected.

For Excel: **File → Download → Microsoft Excel (.xlsx)**. The live Google Sheet
remains the source of truth; an exported Excel file is a snapshot.

## Test before calling the form live

1. On the public website, submit a clearly labelled **TEST** response using
   `launch-test@example.com`, company **TEST Engineering**, all required answers,
   and no real phone number. Confirm the button says **Sending...** then
   **Thanks — your response has been received.**
2. Open **Responses** and verify exactly one new row, a real timestamp, the test
   email and company, and every answer under its matching heading.
3. Try an empty required field and an invalid email: neither should save a row.
   Keep the TEST row marked as test or delete it yourself when done.

The server accepts success only when Apps Script confirms the same submission
ID after writing. Double clicks are blocked; retries with unchanged answers in
the same open form reuse that ID. Google checks IDs under a lock before appending.
Refreshing the page starts a new submission; it is not cross-device deduplication.
If a timeout occurs after Google already wrote the row, retry unchanged answers
in the same page to get the receipt without another row.

Failures retain the answers and show the visible contact email. If setup is
missing, the API returns HTTP 503 `FORM_NOT_CONFIGURED`. Incorrect permissions,
secrets, headers, quotas or unavailable Google responses return failure. An HTTP
200 from Google alone is not treated as success. After changing script code,
use **Deploy → Manage deployments → Edit → New version → Deploy**.

## Technical boundaries and free limits

Browser → `POST /api/feedback` → Apps Script → Google Sheet. No responses are
written to Netlify/Vercel local files, local CSV, browser storage, or a paid
database. The API and script validate lengths, required fields, email syntax,
and allowed options. A honeypot and same-origin checks deter basic spam; this is
not a full anti-abuse service. Spreadsheet formula-looking input is escaped as
text for safe Sheets/Excel viewing. Do not publish the shared secret.

The route uses a 15-second Google timeout; an uncertain receipt can be retried.
There are no new runtime libraries, paid APIs, email services or analytics.
The exact API and Apps Script logic can be tested without contacting Google
with `pnpm test:website` (Node 24).

References: [Google Web apps](https://developers.google.com/apps-script/guides/web),
[Content Service redirects](https://developers.google.com/apps-script/guides/content),
[Apps Script quotas](https://developers.google.com/apps-script/guides/services/quotas).
