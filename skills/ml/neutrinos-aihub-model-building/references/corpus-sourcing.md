# Sourcing and building training corpora when no design partner exists

Method for producing real, usable training data from public sources. Applies whenever a customer
dataset is unavailable and everything must come from the open internet.

## Order of preference

1. **Real domain text with an existing label.** Best case.
2. **Real domain text, labels constructed by auditable rule.** Acceptable if the rules ship.
3. **Aggregate counts / statistics.** Not usable as training rows. Useful only for label taxonomies
   and market-sizing. Never present as training data.
4. **Synthetic text.** Last resort, and state it plainly in every artifact.

## Verify the source is what it claims

Before recommending a dataset, probe it directly — HF datasets API, parquet schema, row count.
Never judge by title or dataset card.

Checks that changed decisions in practice:

- **Field list from a live sample.** An 18M-row complaint database returned only metadata — product,
  issue, company, dates — and **no narrative text column at all**. The largest-looking source was
  useless for anything needing text.
- **Product distribution across a sample.** A 64k-row narrative set had 16 products, none of them
  insurance. Real complaint language, wrong sector.
- **Licence field, not licence prose.** A well-structured 4,713-row policy-contract set had
  `license: None` and publisher copyright. Fine for research, not for a shipped model.
- **Row count for the useful subset.** "291,315 complaint records" can be 291,315 metadata rows
  with zero narratives.

## Licence classes that matter

| Class | Examples | Usable in a product? |
|---|---|---|
| Public domain / CC0 / permissive (CC-BY, Apache-2.0) | US federal complaint data, CUAD, byczong | Yes, with attribution |
| Explicitly non-commercial (MITRE MPQA, CC-BY-NC) | academic opinion corpora | No — research only |
| Publisher copyright, no licence stated | most real policy wordings | Internal training low risk; **redistribution not cleared** |
| Third-party mirror of the above | broker CDNs, aggregator sites | Flag ambiguous, do not silently use |

## Multi-source bias

One source is not a dataset, it is a house style — even at thousands of rows. Measure the largest
single issuer's share of rows. Anything above ~25% means the model learns layout, not content.
Merging three corpora took one model from 68 documents/one issuer to 134 documents/56 issuers with
the top share at 9.6%.

## Extraction: find the real structure, not the keywords

Insurance wordings write clauses as numbered and lettered list items. Split on
`(?:^|\n)\s*(\d+(\.\d+)*[.)]|[a-z]\)|\([ivx]+\)|[\u2022\u25cf\u25aa])\s*` boundaries rather than
searching for type words, then classify each block against type regexes (exclusion, deductible,
copay, sublimit, limit, waiting period, condition, cover).

## Cleaning classes that recur

Filter these every time; they are the difference between a clean set and one that teaches errors:

- **Page furniture** — footers, registered-office addresses, page numbers bleeding into the last
  block of a page.
- **Keyword fragments** — matches a type word but states no clause ("Still subject to
  limits/sub-limits/co-pay/deductibles.").
- **Front matter** — table of contents, index, signature pages.
- **Marketing prose** — matches a type word but is a sales sentence, not a term.
- **Duplicates across overlapping sources** — same clause text in two files.

Require every kept clause to both match a type pattern AND assert something (a verb, a number, a
date, a currency). This typically costs 7–12% of rows. That is the right trade.

## Verify the deliverable yourself

- Magic bytes on every file, not just a count (`head -c 4 f` == `%PDF`).
- Page count and extractable text length per file.
- Read 3–5 verbatim samples from random documents, not the ones the report chose.
- Row count after parsing, not `wc -l` — quoted CSV text with embedded newlines inflates it badly.

## When a source is unreachable

Report it as unreachable **for this host, at this time**, and re-test before it goes into a spec the
user reads. Do not convert one negative result into a standing blocker in an artifact — a WAF that
blocked curl and a real browser cleared within the hour for a subagent.

Escalation ladder when blocked: direct curl → real browser → asset-CDN host → third-party mirror
(flag it) → FOIA/request → a different network path.