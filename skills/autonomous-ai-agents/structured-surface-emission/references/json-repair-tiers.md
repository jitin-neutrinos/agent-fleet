# Repairing malformed fenced-JSON envelopes

Three emission failures account for most real breakage, and all three are
repairable. Recovery is large: a whole long report comes back as a rendered card
instead of raw JSON.

## The failures

| Failure | Looks like | Repair |
|---|---|---|
| Literal newline inside a string value | `Unterminated string` | escape to `\n` / `\r` |
| Missing comma between array elements | `Expecting ',' delimiter` | insert between `]}`/`}` and `[{` |
| String truncated mid-emission | `Unterminated string` at end of body, brackets unbalanced | close the string, then close open brackets |

The third is the model running out of tokens mid-payload. It is the most
valuable to repair: the truncated card often contains most of a report.

## Order matters

Apply cheap, string-level repairs first, then structural ones, then bracket-depth
balancing. Attempt-and-fall-through per tier: each tier is a full parse attempt,
and the first success wins.

## Every pass must be string-aware

A repair that does not track whether it is inside a string literal will corrupt
valid content. The concrete trap: a regex rewriting `],[` or `}{` hits those
sequences inside a `code` block that legitimately contains them, and Python's
`re` emits `FutureWarning: Possible nested set`. Write the pass as a character
scan with `inString` / `escaped` flags — the same discipline a JSON tokenizer
uses.

## Repair changes what parses, so re-run the WHOLE suite

A repair that makes previously-invalid JSON parseable can change which fence run
is read as the closer. In practice: truncated-string repair made inner triple
backticks inside a `code` block parse as a valid card, and a closer-selection
rule that took the FIRST parseable run began truncating cards at those backticks.
The existing suite caught it; a test written only for the new case would not.

The fix that satisfied both: collect all parseable closers and prefer the LAST
(longest body), rather than the first.

## Verify against real payloads

Synthetic approximations of "what a model emits" test the wrong thing and pass
while the live case stays broken. Replay actual stored messages through the
parser and count how many recovered. Note that `state.db` has no `data` column —
messages live in the `messages` table with `session_id` + `content`, and
`node:sqlite` (`DatabaseSync`) is available without adding a dependency.