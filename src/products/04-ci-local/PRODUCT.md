# 04 — CI Local

> Run your CI on your laptop in the exact runner environment, before you push.

| | |
|---|---|
| **Lane** | Open source |
| **Wave** | 2 (months 3–6) |
| **Lead user** | Individual developers |
| **License** | Apache-2.0 |
| **Monetizes via** | Pro tier ($19/mo) for proprietary runner image mirrors |

---

## Pain point

From the Hacker News thread on what developers wish existed in 2026, verbatim:

> *"A sane CI system. I hate writing commands in YAML files, committing them, and then looking at the result. I would love to have access to the same env as the CI so I could prototype the script on my own machine before committing. Solve this and I would pay for it."*

`act` exists for GitHub Actions, but it's incomplete and single-vendor. The category leader has not been crowned. CI Local fills that gap across vendors.

## Target user

- **Primary:** Individual developers who maintain CI configs and feel the frustration weekly.
- **Secondary:** Teams onboarding new engineers — "run the CI locally" is a common first-day need.
- **Tertiary:** OSS contributors fixing CI on a project they don't own.

## Value proposition

*"The exact same image. The exact same env. Run it before you push — break it locally, fix it locally."*

Demo line: **"Stop the commit-push-watch-fail-fix-commit loop. Run CI locally. Use breakpoints."**

## Key features (MVP)

1. **`cilocal run`** — reads `.github/workflows/*.yml`, `.gitlab-ci.yml`, `.circleci/config.yml`, or `.buildkite/pipeline.yml` and reproduces a job locally.
2. **Image-accurate runners** — mirrors of `ubuntu-22.04`, `ubuntu-24.04`, `macos-latest`, `windows-latest` (where licensing allows) plus the GitLab `saas-linux-medium` series.
3. **Breakpoint support** — pause between any two steps, inspect the working directory, modify a command, continue. The killer feature.
4. **Secret injection** — pulls from `.env`, 1Password, AWS Secrets Manager, etc. Doesn't store secrets on disk.
5. **Cache reuse** — local runs reuse the same cache key as the hosted runner so subsequent runs are fast.
6. **Diff against last hosted run** — `cilocal diff <run-id>` compares local execution to the most recent hosted run.

## Design direction

- **CLI-only at v1.0.** No GUI. Developers want this in the terminal where they live.
- **Idempotent and re-runnable.** Killing a run mid-way leaves no orphan containers.
- **One-line install.** `brew install cilocal`, `winget install cilocal`, `curl | sh` for Linux.
- **Vendor-neutral docs.** Same examples for GitHub, GitLab, Circle, Buildkite. The category-leader vibe.

## Monetization

- **OSS core is free forever.** Apache-2.0.
- **Pro tier — $19/dev/mo** — proprietary runner image mirrors that GitHub-hosted larger runners or GitLab SaaS use, plus secret manager integrations.
- **Hosted CI Local** ($49/team/mo) — share runs in a team-visible log; useful for OSS teams debugging together.

## Dependencies

- **Foundation:** none — CI Local is mostly standalone.
- **Shared platform:** only the Pro tier and hosted variant touch shared auth/billing.
- **External:** Docker / containerd / Podman, Firecracker (for micro-VM mode), GitHub Actions toolkit (for accurate event simulation).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `act` adds breakpoint support and CI Local is redundant | Beat them on multi-vendor support; `act` is GitHub-only by design. |
| Image mirroring is legally risky for proprietary runners (Windows, macOS) | OSS tier supports Linux only. Pro tier handles licensing for proprietary images. |
| Container runtime fragmentation makes "exact same env" claim hard | Pin to specific runtime versions per OS; document the assumptions; test against published runner images monthly. |
| The category never gets out of "indie hacker tool" status | Mitigate by becoming the standard via excellent docs, vendor-neutral framing, and OSS-conference speaker slots. |

## Future roadmap

- v1.1: ARM64 native runners (M-series Mac).
- v1.2: workflow generator — "I have a Node project, generate a sane CI starting point."
- v1.3: differential testing — "run the same workflow on N OS versions in parallel locally."
- v2.0: hosted runs for OSS teams (free) — small team-shared runner pool funded by Pro tier subsidies.

## Validation plan (30-day kill criteria)

- Hacker News front page on launch (top 30, ideally top 10).
- 5K+ GitHub stars in 30 days.
- 1K+ daily active users by day 30.
- Funnel from OSS to Pro: 1.5%+ conversion in first 90 days. If <0.5%, kill the Pro angle (keep the OSS).

## Why this in Wave 2

Wave 2 needs **one OSS distribution win** to drive top-of-funnel for paid Wave-1 products. CI Local is uniquely positioned to do that — pure pain, immediate demo, instant viral moment when it works.
