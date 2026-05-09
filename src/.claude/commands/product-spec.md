---
name: product-spec
description: Open the spec for one DevTrust product and summarize its current state and gaps
arguments:
  - name: product
    description: Product name or number (e.g. "smart-test-selector" or "02")
    required: true
---

# /product-spec <product>

When the user runs this:

1. Resolve the product argument to a folder under `products/` (match by number prefix or kebab-case name).
2. Read the product's `PRODUCT.md`.
3. Render a 5-line summary covering: pain point, target user, value prop, key feature, monetization.
4. Then list 3–5 specific gaps in the spec — places where the spec is hand-wavy, contradicts another product, or hasn't been validated with users yet.
5. End with: "Run /product-validate <product> to start a validation pass."

Don't restate the full spec. The user can read it themselves. Add value with the gap analysis.
