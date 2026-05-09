# WhyChanged (`whychanged`)

> Production diff-detective. When monitoring tells you something broke, **what actually changed?**

## Why

Production incidents almost always trace back to *something* that happened in the recent past — a deploy, a feature-flag toggle, a config push, a dependency bump. But your dashboards tell you what's broken, not why. WhyChanged correlates change sources in a time window around an incident and ranks them by likelihood of having caused it.

## Status

**v0.1.0 beta.** Ships the engine + a local Git change provider + the GitHub Deployments cloud provider. Other cloud plugins (LaunchDarkly, Render, Vercel, ArgoCD, Kubernetes events) land in v0.2+.

## What v0.0.1 does

1. Asks every configured `ChangeProvider` for changes in the requested window.
2. Scores each change with a deterministic heuristic:
   - **Recency** — exponential decay relative to the incident time (30-min half-life)
   - **File scope** — bonus when a change touches files that belong to the affected service
   - **Kind weight** — schema migrations and config changes outscore feature-flag toggles when all else is equal
3. Sorts by score and emits a JSON + Markdown report.

## CLI

```bash
whychanged version

# Rolling 30-minute window from now
whychanged explain --repo .

# Explicit incident time + service scope
whychanged explain --repo . \
  --since 1h \
  --incident-at 2026-05-08T14:30:00+00:00 \
  --service api \
  --service-file src/api/models.py \
  --service-file src/api/views.py

# v0.1: combine local commits with GitHub Deployments events
export WHYCHANGED_GITHUB_TOKEN=ghp_...
whychanged explain --repo . \
  --since 2h \
  --github-repo myorg/api \
  --github-environment production
```

Output: `.whychanged/report.json` (versioned, machine-consumable) + `.whychanged/report.md` (human companion).

## Change kinds

| Kind | Source examples |
|---|---|
| `deploy`       | Git commit on main, container release, cloud build |
| `feature-flag` | LaunchDarkly / Statsig / homegrown flag toggle |
| `config`       | Kubernetes ConfigMap, env-var change, infra apply |
| `dependency`   | package.json / requirements update, image bump |
| `schema`       | Database migration / schema change |
| `unknown`      | Catch-all for unclassified providers |

## Roadmap

- **v0.2** — GitHub App installation-token auth + incident-aware webhook receiver: post the top culprit to Slack / Datadog
- **v0.2** — outcome-trained ranker (replaces the deterministic heuristic with a learned model once we have "was the top rank actually the culprit?" data)
- **v0.3** — service-graph integration (rank higher when a change is upstream of the affected service)

## Apache-2.0 license. See [CHANGELOG](CHANGELOG.md).
