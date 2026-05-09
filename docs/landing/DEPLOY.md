# Deploying the DevTrust landing page

`docs/landing/index.html` is a single self-contained file: no build step, no
framework, just inline CSS + a tiny form. You can deploy it to anything that
serves static HTML.

**Recommended: Vercel via GitHub Actions** — set up once, every future
edit to `docs/landing/` auto-deploys. The workflow lives at
[`.github/workflows/deploy-docs.yml`](../../.github/workflows/deploy-docs.yml)
and is already wired; you just need to register a Vercel project and add
three secrets.

## Option A — Vercel via GitHub Actions (recommended)

This is what's wired up by default. The workflow runs `vercel pull/build/deploy`
on every push to `main` that changes `docs/landing/**`, plus on manual
`workflow_dispatch`. Each deploy is a production deploy with a stable URL.

### One-time setup (~5 minutes)

1. **Create the Vercel project:**
   - Go to [vercel.com/new](https://vercel.com/new), sign in with GitHub.
   - Import `AbdullahBakir97/DevTrust`.
   - **Root Directory:** `docs/landing` (use the **Edit** button next to the
     repo path on the import screen).
   - **Framework Preset:** "Other" (Vercel auto-detects static HTML).
   - **Build & Output Settings:** leave all blank — there's no build step.
   - Click **Deploy**. The first deploy uses Vercel's automatic Git
     integration, so it'll be live in ~30 seconds at `*.vercel.app`.

2. **Disable Vercel's automatic Git deploys** so the GitHub Action becomes
   the single source of truth:
   - Project Settings → **Git** → "Connected Git Repository" → toggle off
     **Production Deployments** and **Preview Deployments**. (You can leave
     them on if you want both layers — they don't conflict — but one source
     is cleaner.)

3. **Grab three values from Vercel:**
   - **`VERCEL_TOKEN`** → `vercel.com/account/tokens` → **Create Token** →
     scope: full access. Save the value (shown once).
   - **`VERCEL_ORG_ID`** → `vercel.com/account` → "Your ID."
   - **`VERCEL_PROJECT_ID`** → Project Settings → "Project ID."

4. **Add all three as GitHub Actions secrets:**
   - `github.com/AbdullahBakir97/DevTrust/settings/secrets/actions` →
     **New repository secret** → add each of the three with the names
     above. Spelling matters; the workflow references them verbatim.

### How a deploy fires

Any of these triggers a production deploy:

```bash
# Edit and push:
vim docs/landing/index.html
git add docs/landing/index.html
git commit -m "Tighten the hero copy"
git push                                      # -> auto-deploy

# Or manually from the Actions tab:
# Actions -> "Deploy landing -> Vercel" -> Run workflow
```

The Action's run summary prints the production URL. Set up your custom
domain (`devtrust.dev`) in **Project Settings → Domains** to alias that URL.

### Why this over plain Vercel Git integration

Both work. The GitHub Actions path matters when you eventually add things
that should run **before** the deploy — HTML lint, dead-link check, image
optimization, etc. Easier to extend a workflow you already own than to
migrate later.

## Option B — GitHub Pages (no extra account)

This serves the page from the `docs/landing/` directory of your `main` branch.

1. **Repo Settings → Pages.**
2. **Source:** "Deploy from a branch."
3. **Branch:** `main` · **Folder:** `/docs` (or `/docs/landing` if your Pages
   account supports nested paths — most do).
4. Click **Save**.
5. Wait ~30 seconds. The page is live at
   `https://abdullahbakir97.github.io/DevTrust/landing/` (case-sensitive).

If you'd rather have it at the root URL `https://abdullahbakir97.github.io/DevTrust/`, copy the file:

```powershell
Copy-Item docs\landing\index.html docs\index.html
git add docs\index.html
git commit -m "Mirror landing page at /docs/index.html for GitHub Pages root"
git push
```

Then in Pages, set Folder to `/docs`.

### Custom domain on GitHub Pages

Once the page is live at `*.github.io`, point your real domain at it:

1. Buy `devtrust.dev` (or `.io` / `.ai` if `.dev` is taken). Cloudflare Registrar
   sells `.dev` at cost (~$12/yr) and bundles SSL.
2. **Repo Settings → Pages → Custom domain.** Enter `devtrust.dev`. Tick
   "Enforce HTTPS."
3. In your DNS provider, add:
   - `A` record at `devtrust.dev` pointing to GitHub Pages' IPs
     (`185.199.108.153`, `185.199.109.153`, `185.199.110.153`,
     `185.199.111.153` — current as of 2026, check
     [docs.github.com](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)).
   - `CNAME` at `www.devtrust.dev` pointing to `abdullahbakir97.github.io`.
4. Wait ~10 minutes for DNS propagation. Page is live at `https://devtrust.dev`.

## Option C — Netlify (faster, more polished)

If you anticipate any kind of routing / form handling / serverless functions
later, start on Netlify now.

1. Sign up at [netlify.com](https://www.netlify.com) with your GitHub account.
2. **Add new site → Import from Git → GitHub → DevTrust repo.**
3. **Base directory:** `docs/landing` · **Publish directory:** (leave blank)
   · **Build command:** (leave blank — there's no build).
4. Deploy. Live at `*.netlify.app` immediately.
5. **Domain settings → Add custom domain.** Same DNS setup as above; Netlify
   handles SSL automatically.

Bonus: Netlify Forms gives you a free, serverless form-submission endpoint
(see "Wiring the waitlist form" below) which makes Option B preferable if
you can spend 5 minutes on a free signup.

## Wiring the waitlist form

The `<form>` in `index.html` currently has `action="mailto:hello@devtrust.dev"`
as a fallback. That's lazy — emails go to a domain you might not own yet, and
many browsers don't handle mailto well. Replace it with a real provider.

### Easiest: Tally (no account, free)

1. Go to [tally.so](https://tally.so). Sign in with GitHub.
2. **Create new form** → **Blank form**.
3. Add one field: **Email** (required).
4. **Title:** "DevTrust Cloud waitlist."
5. **Publish.** Tally gives you a public URL like `tally.so/r/abc123`.
6. In `index.html`, replace the entire `<form>...</form>` block with one line:
   ```html
   <a class="btn btn-primary" href="https://tally.so/r/abc123" target="_blank" rel="noopener">Join waitlist</a>
   ```

Submissions show up in your Tally dashboard; export to CSV anytime.

### Slightly fancier: Netlify Forms (if you went with Option B)

1. Add `data-netlify="true"` to the `<form>` tag and a hidden `name` field:
   ```html
   <form name="waitlist" method="POST" data-netlify="true">
     <input type="hidden" name="form-name" value="waitlist" />
     <input type="email" name="email" placeholder="you@company.com" required />
     <button type="submit" class="btn btn-primary">Get early access</button>
   </form>
   ```
2. Re-deploy. Netlify auto-detects the form on the next build.
3. Submissions appear in **Netlify dashboard → Forms** with notification email
   support and Slack webhooks.

### Or: ConvertKit / Substack (if you also want to send email)

If you plan to send "DevTrust Cloud is now live" emails to the waitlist later,
sign up for ConvertKit (free up to 1,000 subscribers) or Substack and use
their embedded form. The trade-off: their embed CSS will look slightly off
against the dark theme; you may need to override colors.

## After deploy, update the README

Once the page is live at its real URL, edit the top-level `README.md` and
replace `https://devtrust.dev` with the actual URL (Pages, Netlify, or your
custom domain). Then push:

```powershell
git add README.md
git commit -m "Point Cloud waitlist link at the live landing page"
git push
```

That's it. Your landing page is real, your waitlist captures real signups, and
the README sends visitors to the right place.

## Analytics (optional, ~5 min)

If you want to know how many people actually visit the page:

- **[Plausible](https://plausible.io)** — privacy-friendly, $9/month, one
  `<script>` tag at the end of `<head>`. Free 30-day trial.
- **[Cloudflare Web Analytics](https://www.cloudflare.com/web-analytics/)** —
  free, no script (uses HTTP headers). Works automatically if your DNS is on
  Cloudflare.
- **GitHub Pages traffic** — Repo Insights → Traffic. Built-in, basic.

Don't bother with Google Analytics. It adds privacy overhead, slows the page,
and the data isn't actionable at this stage.

## Done

You've got: a public landing page, a captured waitlist, optional analytics,
and a clear path from `pip install devtrust-apr` → "Tell me when DevTrust
Cloud is live." That's the full top-of-funnel for the platform.
