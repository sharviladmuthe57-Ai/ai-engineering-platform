# Kairo Labs — Netlify Free launch

The user approved **Netlify Free**, replacing the original Vercel request.
Budget: **₹0 / $0**. Never enable a paid plan, trial requiring payment,
auto-recharge, extra credits, a payment method, paid domains or paid integrations.
If any of those is required, stop. Do not silently change providers.

Netlify's Free plan permits commercial projects and has a hard credit cap with
no auto-recharge option. At the cap, projects pause rather than create an overage
bill. It is not unlimited availability. Keep all optional add-ons off. New free
projects may include Netlify's provider badge; do not pay to remove it.

## Import the existing GitHub repository

1. Sign in to [Netlify](https://app.netlify.com/) using your own account. Verify
   that the selected team's plan explicitly says **Free ($0)**. Do not use a paid
   team or switch an existing team's billing settings without authorization.
2. Choose **Add new project → Import an existing project → GitHub**. If GitHub
   requests new access, the owner must approve access only to this repository:
   `sharviladmuthe57-Ai/ai-engineering-platform`. Do not grant every repository.
3. Use the existing **main** branch. Base/root directory is the repository root
   (leave blank), not `src`, `public`, `static`, or the Python application.
   Choose a free project name such as `kairo-labs` if available, otherwise
   `kairo-labs-ai` or `kairo-engineering`. Netlify supplies a `.netlify.app` URL.
4. Netlify should detect **Next.js**. `netlify.toml` sets build `pnpm build`,
   publish directory `.next`, Node 24. Keep the automatic Next.js adapter.
   Do not deploy a static export: that would remove the form's API handler.
   Do not enable Netlify Forms, Database, AI Gateway, or paid plugins.
5. Add the two private Google environment values following
   [Google Sheets setup](google-sheets-form-setup.md), if they are available.
   Missing values deliberately leave the form in a truthful error state.
6. Deploy only after confirming **Free**. In **Deploys**, verify the deployment
   uses the intended `main` commit and finishes successfully. Open the exact
   reported public URL; do not assume a project name became the live URL.

Future pushes to GitHub main should automatically deploy. Confirm Git integration
and the production branch in Netlify; a GitHub push alone does not prove a public
deployment. No separate engineering repository is needed.

## Release checks

- Run `pnpm build`, `pnpm test:website`, and the existing 49 Python unit tests.
- Inspect `git status` and `git diff`; stage only intended website sources,
  documentation, tests and configuration. Keep `.env.local`, `.netlify`, `.next`,
  dependencies, runtime jobs, and unrelated untracked Python helpers out of Git.
- Confirm the public deployment's commit equals `git rev-parse HEAD` and the
  remote `refs/heads/main` after pushing.
- Check desktop, laptop and mobile: Kairo Labs title/nav/footer, visible email,
  seven video chapters, aligned 2D stages, 3D Vision/Next transitions in both
  directions, editor export, navigation, and no major console errors.
- Confirm all public assets return 200 and the actual Google TEST row appears
  before calling form storage live. Mocked tests do not prove a live Google row.

The frozen FastAPI/CV/rules/placement/routing backend stays local and unchanged.
The public site's editor is the existing labelled read-only product export, not
the interactive Python app and not a new 3D product.

References checked during launch:
[Netlify Free commercial use](https://www.netlify.com/blog/introducing-netlify-free-plan/),
[Free credit hard limit](https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/),
[Next.js adapter](https://docs.netlify.com/build/frameworks/framework-setup-guides/nextjs/overview/).
The original Vercel Hobby target was stopped because its
[fair-use rules](https://vercel.com/docs/limits/fair-use-guidelines) restrict
commercial startup marketing use to paid plans.
