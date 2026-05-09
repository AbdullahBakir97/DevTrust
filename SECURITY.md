# Security policy

> If you believe you've found a security vulnerability in DevTrust, please **do not open a public GitHub issue**. Use a private channel so we can fix the issue before it's exploited.

## Reporting a vulnerability

The fastest, most reliable channel is **GitHub Security Advisories**:

1. Go to <https://github.com/AbdullahBakir97/DevTrust/security/advisories/new>
2. Fill in the form with as much detail as you have
3. We'll acknowledge receipt within **3 business days** and provide an initial assessment within **7 business days**

If GitHub Security Advisories is unavailable to you, email **abdullah.bakir.1997@gmail.com** with subject line `[DevTrust security]`. PGP key on request.

## What to include

A useful report has, at minimum:

- Which DevTrust product is affected (or `multiple`)
- The version (or commit SHA)
- The class of issue (RCE, auth bypass, info-disclosure, prompt injection, supply-chain, etc.)
- A minimal reproduction (commands, sample input, expected vs. actual)
- Whether the issue requires authentication / specific environment / specific data
- Whether you'd like credit in the advisory (and the name to credit)

If you can't produce a full PoC, a clear explanation of the bug class and where you observed it is still helpful.

## Scope

| In scope | Out of scope |
|---|---|
| All DevTrust products in `src/products/` | Issues in third-party dependencies (file with that project; we'll mirror) |
| Workspace tooling (CI, pre-commit, infra-as-code) | Issues in the user's own code that DevTrust analyzes |
| Documentation that, if incorrect, would lead users to insecure setups | Theoretical issues with no realistic exploit path |

## Coordinated disclosure timeline

Our default timeline for coordinated disclosure:

| Day | What happens |
|---|---|
| 0 | Report received, acknowledged |
| 7 | Initial assessment, severity assigned, fix planned |
| 14–60 | Fix developed, tested, released; private advisory drafted |
| 60–90 | Public advisory published with credit; affected versions documented |

We'll work with you on a different timeline if there's a strong reason (active exploitation, regulatory deadline, etc.).

## Severity guide

We use the [CVSS 4.0](https://www.first.org/cvss/v4-0/) score for severity. As a rough triage guide:

| Severity | Examples |
|---|---|
| Critical (≥9.0) | Remote code execution; auth bypass on authenticated endpoints; secret-leak; agent escapes its sandbox |
| High (7.0–8.9) | Stored XSS; privilege escalation; prompt-injection that exfiltrates data; SQLi in non-public endpoints |
| Medium (4.0–6.9) | Reflected XSS; CSRF on state-changing endpoints; predictable resource locators; mis-scoped permissions |
| Low (<4.0) | Info-disclosure of non-sensitive data; rate-limit issues; weak defaults |

## Out-of-band advisories

When we publish an advisory, we'll:

- File a CVE if the issue meets MITRE's threshold
- Cut a patched release of every affected product
- Push a notice to subscribers of the affected GitHub repo
- Update CHANGELOG entries and pin minimum-safe versions in dependent products

Thank you for helping keep DevTrust users safe.
