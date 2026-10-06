# Cache TTL + provider-default audit

## What to measure first (before touching any config)

Read the live proxy/upstream stats, never the harness config alone:

- `cache_read_tokens`, `cache_write_tokens`, split by provider
- `observed_ttl_buckets` — which TTL buckets writes actually landed in
- `uncached_input_tokens` — the true fresh-input volume
- `route_counts.cache_hit` vs `cache_miss` — the real hit rate
- `compression_vs_cache` — `tokens_saved_by_compression`,
  `tokens_lost_to_cache_bust`, `cache_bust_count`

## The default-TTL trap

Anthropic silently changed the default prompt-cache lifetime from 1 hour to
5 minutes around March 2026, producing a documented wave of unexpected cost
inflation. A harness that does not set a TTL explicitly inherits whatever the
provider currently defaults to, so the setting must be pinned per harness, not
assumed.

Two things to establish before concluding anything is wrong:

1. **Which bucket did writes actually land in?** If `cache_write_5m_tokens` is 0
   and `cache_write_1h_tokens` is non-zero, the long TTL is already in force —
   possibly applied by a shared proxy rather than by the harness's own config.
2. **Is a proxy load-bearing for cost?** If every harness routes through one
   proxy, the proxy may be what pins the TTL. That is working, but it makes the
   proxy cost-critical, not merely a compression convenience — say so plainly.

A healthy stack looks like: all writes in the long bucket, hit rate above ~90%,
and uncached input a small fraction of total input. When that holds, the audit
finding is "nothing to fix", which is a legitimate and useful result — report it
with the numbers rather than inventing a change.

## Interference: compression vs caching

Compressing text that sits inside a cached prefix invalidates that prefix, so the
saving is partly paid back as cache writes. Compare:

```
bust_ratio = bust_write_tokens / saved_by_compression
```

A ratio near 1 means most of the compression benefit is being returned. Report
it; do not "fix" it by disabling compression without a measured decision, since
upstream net-token figures may still show a win.

## Per-provider asymmetry is normal, not a bug

Free/local models (e.g. Ollama-served models, or plan tiers with zero marginal
cost) can show cache writes with zero reads and zero cost. That is expected —
record them at $0 and keep them visible so the dashboard does not look broken.
Do not force them onto a priced provider's rate.

## Reporting shape

State the measured numbers first, then the conclusion, then what you changed (if
anything). When an audit finds no defect, say so plainly and give the evidence
that justified stopping — a verbose list of unfixed hypotheticals reads as
unfinished work.
