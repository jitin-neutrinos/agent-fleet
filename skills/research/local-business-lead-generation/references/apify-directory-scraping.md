# Apify directory scraping — actor selection, schema discovery, cost model

Notes for scraping business directories (JustDial, Sulekha, IndiaMART, Practo) via
Apify. Apify is a marketplace, so the same site has many actors of wildly different
quality; pick by MEASURED phone yield, never by store popularity.

## Actor comparison (JustDial, measured on the same category)

| Actor | Phone yield | Notes |
|---|---|---|
| `themineworks/justdial-business` | **~86%** | Per-item event price, IN residential proxy default, "Plaintext Phone, No Login". Uses the XHR the site fires after the "Show Number" tap. The one to use. |
| `codingfrontend/justdial-business-search-scraper` | 0% | Takes raw category URLs, but bot protection kills it: every request failed with "No Justdial listing API records were observed". Avoid. |
| `thirdwatch/justdial-business-scraper` | ~4% | Cheap and reliable for names/addresses/coords, but its output has `phone: ""` — the directory masks numbers on search pages. Useful ONLY for coordinates + the ID needed to fetch detail pages. |

The masked-vs-plaintext split is the whole game on Indian directories: search pages
embed `"mobile":""` server-side and reveal the number via an XHR. An actor that only
parses the HTML gets empty strings and looks broken; one that drives the click gets
real numbers. Check the actor's own README for a "plaintext phone" / "no login"
claim, then still measure it.

## Input schema discovery

`GET /v2/acts/<user>~<name>` and `.../input-schema` both 404 for actors whose build
is a git repo. The working paths:

- `GET /v2/acts/<a>/versions` → list `versionNumber`s, then
  `GET /v2/acts/<a>/versions/<v>` for the source files.
- If `sourceFiles` comes back EMPTY (git build), fetch the published markdown
  instead: `https://apify.com/<user>/<name>.md` — the `# Actor input Schema`
  section plus a runnable input example. This is the reliable route.

## Cost model

Per-event pricing pages quote cost per ITEM. Real spend per query was ~24x that,
because a run also consumes residential proxy transfer and platform usage:

```
measured_cost_per_query = sum(run.usageTotalUsd) / successful_runs
affordable_queries      = (plan_allowance - already_spent) / measured_cost_per_query
```

Read the balance from `GET /v2/users/me` (`plan.monthlyUsageCreditsUsd`,
`maxMonthlyUsageUsd`; a free account is a $5 monthly allowance) and running spend
from `GET /v2/users/me/usage/monthly` (sum `amountAfterVolumeDiscountUsd` across
`monthlyServiceUsage`). Re-check mid-sweep — it is the only stop condition.

## Parallel sweep shape

One run per query (category x locality) so a single failure is isolated; 3
concurrent runs was stable, more risked rate limits. Append
`{query, run_id, status, dataset_id, cost_usd}` to a JSONL per completion so the
sweep is resumable and cost is auditable while it runs. Fetch all datasets at the
end with a thread pool (8 wide), then filter.

## Two-step extraction when no actor reveals phones

If every available actor masks numbers, do it in two passes: scrape listings for
names + coords + listing IDs from any cheap actor, then fetch each DETAIL page (or
its API) for the number, budgeting for the second pass. Coordinates from pass 1 also
give you the radius filter for free.