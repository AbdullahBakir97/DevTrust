# Hooks

Claude Code / Cowork hook scripts live here. None are configured yet.

## Planned hooks (Wave 1)

- **on-product-spec-edit** — when a `products/NN-name/PRODUCT.md` is edited, ensure the change is reflected in the master plan (`docs/DevTrust-Master-Plan.md`) by flagging a manual sync task.
- **on-wave-update** — when a wave plan is updated, recalculate the dashboard scoring and regenerate `docs/dashboard.html`.
- **pre-commit** — block commits that contain obvious secrets (AWS keys, OpenAI keys, GitHub tokens) using a regex sweep.

When a hook is added, place the script here and reference it from `.claude/settings.json` under a `hooks` key.
