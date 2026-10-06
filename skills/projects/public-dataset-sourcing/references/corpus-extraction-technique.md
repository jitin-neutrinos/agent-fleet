# Getting real clause corpora out of documents and websites

Techniques for building a document-field-extraction training corpus from real published
documents. Every rule here was paid for by a defect found on inspection, not by theory.

## Crawl the sitemap, not the landing page

A site's downloads page is JS-gated and returns nothing to curl. Its `sitemap.xml`
usually lists every product page as plain `<loc>` entries.

```bash
curl -s -m 45 -A 'Mozilla/5.0' -L 'https://<insurer>/sitemap.xml' \
  | grep -oE '<loc>[^<]*</loc>' | sed 's/<[^>]*>//g' | grep -iE 'policy|wording|insurance-policy'
```

One sitemap gave 64 policy pages from a site whose `/downloads` page returned empty.

## Fetch in parallel, and write incrementally

A 64-page sequential scrape at 25s timeout each runs past any background-job cap and
loses everything if it only writes at the end. Use a thread pool and checkpoint every N
pages so a timeout never discards completed work.

```python
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=10) as ex:
    for i, rec in enumerate(ex.map(work, pages), 1):
        records.append(rec)
        if i % 10 == 0:
            json.dump(records, open(OUT, 'w'), indent=1)   # checkpoint
```

An early serial version was killed at ~900s having written nothing. The parallel version
finished the same work in well under the cap.

## Split clauses on the numbering, not the tag

Wordings write clauses as `12.`, `12.3)`, `a)`, `(iv)` and bullets. Splitting on
closing `</li>` or `</p>` returns near-zero clauses because modern sites wrap clause text
in deeply nested `div` card components. Split on the *start* pattern instead:

```python
BLOCK = re.compile(r'(?im)^\s*(?:\d{1,2}(?:\.\d{1,2})*[\.\)]\s+|[a-z]\)\s+'
                   r'|\([ivx]+\)\s+|[•\u2022\u25cf\u2023]\s*)(?=\S)')
```

Going from `<li>`/`<p>` matching to this lifted one corpus from 115 clauses over 64 pages
to 2,159 clauses over 66 documents.

## Classify with an ordered cascade, not a flat alternation

Ordered patterns, most-specific first. A flat union attributes every clause containing
"limit" to `limit`, burying the real exclusions.

```python
CLAUSE_TYPES = [
    ('exclusion',      re.compile(r'(?i)\b(exclusion\w*|excluded|shall be excluded|not covered)\b')),
    ('waiting_period', re.compile(r'(?i)\b(waiting period|moratorium|grace period)\b')),
    ('sublimit',       re.compile(r'(?i)\b(sub-?limit|room rent|per (?:day|policy period) limit)\b')),
    ('copay',          re.compile(r'(?i)\b(co-?pay\w*|co-?payment|deductible amount|franchise)\b')),
    ('deductible',     re.compile(r'(?i)\b(deductible|excess|co-?insurance)\b')),
    ('limit',          re.compile(r'(?i)\b(sum insured|limit of indemnity|not exceeding)\b')),
    ('condition',      re.compile(r'(?i)\b(subject to|provided that|only (?:on|if|where))\b')),
]
```

Then require an **action verb or a number** as well as a keyword, so the row actually
asserts something:

```python
ACTION = re.compile(r'(?i)\b(shall|will|is|are|not|exclud\w*|cover\w*|pay\w*|'
                    r'deduct\w*|limit\w*|\d+%|\d+\s*(?:days?|months?|years?))\b')
```

## Two defect classes to filter after extraction

Both appear the moment you run `pdftotext` over a real corpus, and both teach the model
noise.

**Page furniture merged into the last block.** The final element on a page is often the
registered-office footer, so a waiting-period row arrives carrying
`Acko General Insurance Limited, 2nd Floor, #36/5, Hustlehub One East`. Strip a
trailing footer match, but only when it appears past ~80 characters so a legitimate
address inside a clause survives.

```python
FOOTER = re.compile(r'(?i)(registered\s*(&\s*corporate)?\s*office|CIN\s*[:\-]|'
                    r'company\s*reg|all rights reserved|IRDAI\s*Regn|'
                    r'www\.[a-z]+\.[a-z]{2,}|\d+\s*(?:th|st|nd|rd)\s*(?:floor|flr)\b)')
t = FOOTER.sub('', t) if FOOTER.search(t) and FOOTER.search(t).start() > 80 else t
```

**Keyword fragments that state no clause.** `"Still subject to limits/sub-limits/co-pay/
deductibles."` matched four clause types at once and was labelled `copay`. Reject blocks
that are a bare cross-reference:

```python
FRAGMENT = re.compile(r'(?i)^[\W_]*(?:still\s+subject to|subject to\s*$|note\s*[\.\:\-]|'
                      r'for\s+details\s+refer|please\s+refer|as\s+per\s+annexure|'
                      r'see\s+(?:also\s+)?(?:section|clause|annexure))')
```

Filtering both cost 171 of 2,330 rows. Take the loss: the platform asks a human to
confirm ~25 entries, and a human confirms by reflex. **A smaller clean corpus beats a
larger noisy one.**

## Audit by reading rows, not by counting them

Print three rows per class and judge them. Two defects above were invisible to every
count. Also report the largest single source's share:

```python
print(f'largest single issuer share: {df.issuer.value_counts().iloc[0]/len(df)*100:.1f}%')
```

A corpus that is 100% one insurer is a house-style bias, not a dataset, and the number
makes that argument to a stakeholder without adjectives.

## Confirm a subagent's corpus before trusting it

A research subagent reporting "76 PDFs, all verified" gets checked in three cheap calls:
magic bytes on every file, a `Counter` over the manifest's quality/issuer columns, and
one real clause read straight out of a PDF with `pdftotext -f 5 -l 5`. All three caught
nothing wrong here, which is exactly why the checks are worth running — the corpus arrived
from a hostile environment (dynamic insurer sites) and needed no repair.

## Harvest taxonomies from mirrors when the regulator is walled

`irdai.gov.in` blocked both curl and a real browser, yet the authoritative label set was
obtainable from a mirror: the Insurance Ombudsman Rules 2017 on the Council for Insurance
Ombudsman's own site. **Taxonomies are republished by industry bodies, courts and ombudsman
services.** When the regulator is unreachable, look for the rules document that the
regulator itself administers rather than concluding the taxonomy is unobtainable.

Check the harvested list against any taxonomy already written into a deliverable. Plausible
invented category names look fine until a statutory list arrives and half of them turn out
not to exist.
