# agtrace - changelog

All notable changes to `agtrace` are documented here. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [SemVer](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2026-05-08

### Added
- **Public hooks** for cross-product integrations:
  - `agtrace.current_span()` returns the active `SpanHandle` or `None`.
  - `agtrace.attach_attributes({"k": v, ...})` pins attributes on the active span; returns `True` iff a span was active.
  Both safe to call any time; never raise. Designed for libraries (like `tokencost`) that want to enrich an in-flight span without taking it as a parameter.
- Re-exports `current_span` + `attach_attributes` at the package root for ergonomic imports.
- 5 new tests: `current_span()` outside / inside blocks, attribute attachment with type coercion, no-op behavior outside blocks, version assertion.

### Notes
- Schema unchanged. Just version bump 0.0.1 -> 0.0.2.
- The hooks are intentionally minimal -- they expose the internal `ContextVar` indirectly so external code stays decoupled from `agtrace`'s internals.

[0.0.2]: https://github.com/AbdullahBakir97/agtrace/compare/v0.0.1...v0.0.2

---

## [0.0.1] - 2026-05-08

### Added
- Initial scaffold: `agtrace` Python package with two CLI commands (`dump`, `version`).
- Pydantic v2 schema (versioned 0.0.1): `Span`, `SpanEvent`, `Trace` with six AI-tuned span kinds (`agent`, `prompt`, `tool_call`, `retry`, `fallback`, `unknown`).
- `Tracer` with a context-manager API. Spans nest automatically via `ContextVar` so async + threads + nested agent calls all build the right tree.
- Exception isolation: an exception inside a span flips `status` to `error` and records `exception.type` as an attribute, but the exception itself still propagates -- the tracer never silently swallows errors.
- Exporter interface: `SpanExporter = Callable[[Span], None]`. Default is `jsonl_exporter(path)` which appends one JSON line per span. `in_memory_tracer()` is the test-friendly variant.
- Exporter-failure isolation: an exporter that crashes (disk full, queue down) is logged but never breaks the user's code path.
- CLI `dump` command renders a span tree as a Rich tree, including durations and span attributes.
- 14 smoke tests covering: schema/version assertions, root-span generation, nested-span trace+parent chaining, attribute + event setters, exception status handling, exporter-failure isolation, JSONL round-trip, default-tracer path resolution, CLI version + dump + empty input, in-memory tracer ordering, span_kind persistence.
- Apache-2.0 license, hatchling build, typer/rich/pydantic deps.

### Notes
- Wave 3 product. Completes the trio (whychanged + tokencost + agtrace) covering the three observability concerns of the AI era: what changed, what it cost, what the agent did.
- Span IDs follow OpenTelemetry's widths (16-byte trace_id, 8-byte span_id rendered as hex) so future OTLP exporters can hand the trace off to a generic OTel collector without ID rewrites.
- The package intentionally does NOT depend on or import `opentelemetry-*`. v0.1 will add an optional `[otel]` extra so apps that already run an OTel collector can ship spans into it.

[0.0.1]: https://github.com/AbdullahBakir97/agtrace/releases/tag/v0.0.1
