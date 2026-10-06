# Regex scanner state machines (regex crate has no lookahead)

For porting a Python `re` scanner that uses lookahead, backtracking, or `finditer`
into Rust — the regex crate has none of those three. Every rule below was measured on real
gateway-module ports where a wrong port passed a hand-written golden for days.

## Why a scanner at all

`(?=…))`, `(?!…)`, `.*?`, and `\S+?` have no regex-crate equivalent. Options, in order of
preference:

1. **Keep the regex, drop the lookahead** — split the pattern into a matching part plus a
   boundary check the code applies after the match.
2. **Hand-write a two-step scanner** — match the body, then cut at the boundary. What the
   rules below assume.
3. **Prefer stdlib** — `regex` (not `regex-lite`) has real lookahead and lazy repetition.
   If the crate is already a dependency, this is strictly better than rule 2. If adding it is
   the only way to get the parity, that is a real reason; weigh the dep against the ~60 lines
   a scanner costs, and say which you chose in the ledger row.

## The cursor contract (the hang rule)

`finditer` steps one character past a FAILED attempt and keeps scanning. Your loop must too.

```rust
// WRONG: rejected match is re-found at the same offset -> infinite loop
let Some(tag) = find_media_keyword(chars, i) else { break };
if !valid(tag) { i = tag.start(); continue; }        // never progresses

// RIGHT: advance past the KEYWORD, not the match start
let Some(kw) = find_media_keyword(chars, i) else { break };
if !valid(kw) { i = kw.kw + 1; continue; }
```

Three hangs seen across two modules, all worth recognising instantly:

- **Re-seek at the rejected start.** As above.
- **Token scan with an UNBOUNDED read.** `chars[i..].iter().take_while(|c| !c.is_whitespace() …)`
  with no end bound never terminates. Bound the scan by `e < chars.len()` and let the guard
  encode exactly what the reference's class EXCLUDES — nothing more. `\S` excludes whitespace
  and nothing else, so quote and fence are IN the token; adding them to the guard is its own bug
  (see the bridge note below — it makes a later whitespace-bridge unreachable). Measure the class
  from the reference, never from what "looks like a delimiter".
- **Two-position helper returning a bare tuple.** See the next section.

## Returning two positions

A scanner helper that must report both "where the match starts" (which may include a leading
quote run) and "where the keyword is" will be destructured wrong, and the swap compiles clean.

**Return a struct, then delete the tuple version.** `Match { start, kw }` makes the mistake
unrepresentable; a `(usize, usize)` is not a type error, just a hang or a silently rewound
cursor. If you ship the struct, remove the tuple helper in the same edit — leaving both means
the next call site picks the wrong one.

```rust
struct MediaKeyword { start: usize, kw: usize }   // never a bare tuple
let Some(MediaKeyword { start: match_start, kw: kw_at }) = find(chars, i) else { break };
```

Spell BOTH names at every call site even with the struct. Destructuring to `_` for the one you
don't use there is the shape that hides a future rename.

## Span boundaries the regex hides

Getting the SPAN right matters more than the match test, because spans are deleted from the
original text. Verify numerically against the reference
(`[(m.span(), m.group(k)) for m in RX.finditer(text)]`) — never by reading the regex.

- **A quoted path's closing quote is INSIDE the span in one pattern and OUTSIDE in another.**
  Two regexes in the same module disagree on this; read each one.
- **An optional trailing run is part of the match** — `["'\*_]{0,3}\.?` and friends.
- **The match starts at the LEADING quote run**, not the keyword: walk back at most N chars.
- **A lookahead's consumed characters are NOT in the span** unless a later group re-consumes
  them. A sentence-final `.` matched by the `\.(?:\s|$)` arm and then re-matched by the
  trailing `\.?` ends up INSIDE the span — `MEDIA:/x/a.png.` is `0..17`, not `0..16`.
- **The trailing `["'\*_]{0,3}\s*` run is NOT walked into the span.** `MEDIA:/x/a.pngSome text`
  is `0..20` — the span ends where the VALIDATED PATH ended, one character SHORT of the regex
  match (`0..21`). Deleting the span leaves `" text"`, leading space intact. Walking the tail
  into the span turns that into `"text"`: a one-character over-delete that reads as a plausible
  "cleaner" span and silently eats a space on every such row.
- **Lazy quantifiers are FIRST-match-wins.** In `\S+?(?:[^\S\n]+\S+?)*?\.(?:ext)` the `+?`/`*?`
  are lazy, so the match ends at the FIRST known extension — a whitespace-bridging loop that
  keeps extending past it will find the NEXT tag's extension and merge two tags into one span
  (`MEDIA:/a.png, MEDIA:/b.jpg` must be two spans, not one). Return from the scan the moment a
  known extension terminates the token.

### Terminator trimming: what is inside the extension

The extension lookup runs against the token with its trailing terminator run removed, and
getting the trim wrong fails in both directions:

- Trim a **non-dot** terminator (`,` `;` `:` a CJK mark) — it is genuinely outside the match.
- Do **NOT** trim a trailing `.` for the lookup. The lookahead's `\.(?:\s|$)` arm accepts it
  and the trailing `\.?` puts it back INSIDE the span, so `/tmp/a.png.` still ends its
  extension at the `g`. Trimming it makes the lookup see `.png.` — an unknown extension — and
  the whole tag stays visible where the reference strips it.
- Report the extension end as the **end of the trimmed body**, never the dot's index. Returning
  the split index puts the caller mid-path, where the delimiter check fails and the tag is
  dropped.
- The scan bound must be INCLUSIVE of the token end (`1..=body.len()`). An exclusive bound
  rejects exactly the extensions that end the token — which is all of them.
- **The trimmed length is measured in the RAW token, and the LOOKUP runs on the normalized path.**
  These are two different strings. `_normalize_media_tag_path` ends with
  `rstrip("`\"',.;:)}]")`, so `/tmp/a.png,` normalizes to `/tmp/a.png` and its extension end is 10 —
  the raw token is 11. Hand the lookup the normalized string (so the extension test sees `.png`)
  and return an offset in the RAW token (so the caller's delimiter check looks at the real
  character there). Returning the normalized LENGTH when the raw token is longer puts the caller
  mid-token, and trimming the dot before the lookup makes the test read `.png.` — unknown — so the
  whole tag stays visible.
- **Terminators NOT in the normalize set must be trimmed for the lookup only, and the span still
  ends BEFORE them.** The reference's rstrip is ASCII-only: `/tmp/a.png。` normalizes to itself,
  because the CJK marks and `[` live only in the regex lookahead classes. So the extension test
  needs them removed (`png`, not `png。`) while the span's end offset does not move — the reference
  reports 0..16 for all of `/tmp/a.png,`, `/tmp/a.png]`, `/tmp/a.png。` and `/tmp/a.png[`. Adding
  the trimmed characters back is the same one-character over-delete as walking the trailing run.

### Two patterns, two lookahead classes

Sibling patterns over the same keyword routinely have DIFFERENT delimiter classes. A cleanup
pattern's `(?=[…`"'*_,;:)\]}[…]|\.(?:\s|$)|$)` and an extension-less pattern's
`(?=[`"'\s,;:)\]}<CJK>]|MEDIA:|$)` differ in the `[` member and the dot arm. Sharing one
predicate makes a case match in the narrower pattern that the reference rejects. Give each
pattern its own predicate function and let both call sites sit next to each other so the
divergence is visible.

**Two similarly-named reference predicates are NOT interchangeable, even when one looks like a
wrapper around the other.** `known_extension` is regex-shaped — it stops its walk at a lookahead
terminator, so `/tmp/a.png[` answers true. `path_lacks_deliverable_extension` is a raw
`Path(p).suffix` call, so it reads `.png[`, answers false, and routes the tag to the validated
pass. Aliasing the second to `!first` silently merges two different classifications. When a port
has two same-purpose-looking predicates, read each one's body and confirm they differ.

### Constant tables carry a representation convention — measure it, do not infer it

A set-table's elements are stored in ONE convention (dotted, undotted, prefixed, lowercased),
and a port that stores them in another misses EVERY lookup while looking structurally correct.
`MEDIA_DELIVERY_EXTS` holds `'.png'`, not `'png'`, and `Path(p).suffix` also yields `'.png'`, so
the comparison is a bare membership test with no dot-stripping on either side — a port holding
`'png'` rejects every known-extension tag at once. Two follow-ons compound it: the candidate slice
must include the dot (`body[split - 1..]`, not `body[split..]`, when `split` indexes the character
AFTER the dot), and the element's case convention must match the comparison's `.to_lowercase()`
placement. Read one element out of the live reference, print its `repr`, and copy that.

### The leading run's quote is not the path-group opener

A pattern's leading `["'*_]{0,3}` run sits BEFORE the keyword, but the quoted-path ALTERNATIVE
starts AFTER it. `` `MEDIA:/nope` then MEDIA:/tmp/a.png `` has its backtick at index 0 and
`MEDIA:` at 1, and the reference matched it with the BARE `\S+?` class — one span `0..35` that
swallows the trailing tag — not with the quoted alternative, which would have produced two spans.
Starting `p` at the leading run's quote and reading it as a path-group opener splits the match.
`p` starts after the keyword; the leading run only sets the span's START.

### Three distinct end offsets — and the span uses the THIRD

A helper that extends-and-validates produces a THIRD offset that is neither the regex group end
nor the match end, and conflating any two of them is off by a character or more:

- **group end** — where the lazy capture stopped (`MEDIA:/tmp/a b c.kmz` → 12, the path is `/tmp/a`);
- **match end** — group end plus the pattern's trailing `` ["'*_]{0,3}\s* `` run (→ 13);
- **validated-candidate end** — where the extension ladder settled (→ 14).

The span the reference reports is `(match.start(), candidate_end)` — **the ladder's answer, not
the match's**. Three offsets, and the span uses the third. `MEDIA:/tmp/a b c.kmz` matches `0..13`
whose group ends at 12, yet the reference reports `0..14`. Reporting `match.end()` here is
off by one in the direction that DELETES a character you should have kept. The candidate end is
observable only through the validator CALL LOG, so record that log in the golden rather than
reconstructing the candidate on the runner side (a runner that re-derives a value hides every bug
inside it).

**A span boundary is an offset, so measure it — never read it off the pattern text.** This is the
recurring failure mode on this whole class of scanner: inferring which of the three offsets applies,
"fixing" the port to match the inference, and shipping a one-character over- or under-delete that
survives every hand-written unit test. Two wrong inferences in a row is the normal cost. The
one-call measurement that ends it prints all three numbers side by side:

```bash
python3 -c "
import sys; sys.path.insert(0,'hermes-ref')
import gateway.platforms.base as PB
t='MEDIA:/tmp/a b c.kmz'; m=PB._mask_media_scan_text(t)
x=list(PB.MEDIA_EXTENSIONLESS_TAG_RE.finditer(m))[0]
print('match',x.span(),'group',x.span('path'),'candidate',PB._extensionless_media_matches(m)[0][2])"
```

Read that triple, then decide which number the span uses. Do not reason forward from the pattern.

## Extraction ladders: read the body, not the docstring

When a reference helper progressively extends a path and validates each candidate, port the
EXACT bound and stop conditions. A real one: validate the captured path; if it fails, extend
across single spaces up to 8 tokens, never past a newline or the next `MEDIA:` keyword, and
return the first candidate that validates. An unbounded or differently-bounded port either
accepts paths the reference rejects (prompt-injection surface) or loops.

The ladder's answer is the CANDIDATE end — a third offset distinct from both the regex group end and
the match end, and the one the SPAN uses. See "Three distinct end offsets" above; the measurement
recipe there is the first thing to reach for when a span boundary disagrees by one character.

**Only the LAST bridged piece has to satisfy the predicate.** `(?:[^\S\n]+\S+?)*?` is lazy, so a
piece without a known extension is not the end of the match — the engine keeps extending. Two
opposite errors here, both measured: requiring EVERY piece to carry a known extension stops the
walk early (`` `MEDIA:/nope` then MEDIA:/tmp/a.png `` bridges `/nope\``, `then` and
`MEDIA:/tmp/a.png`, and only the last one ends in `.png`), and returning as soon as one piece
satisfies it merges two tags into one span when a terminator — not whitespace — should have ended
the match. A comma ends the run BEFORE any bridging, which is why `/tmp/a.png, MEDIA:/tmp/b.jpg`
is two spans: the first token already terminated.

**A rejected candidate must still be followed by a matching one**, so the cursor advances past
the KEYWORD on failure and past the MATCH END on success. Advancing to `kw_at + 1` after a
success re-finds the same keyword and never reaches a keyword GLUED onto the current one
(`/tmp/a.pngMEDIA:/tmp/b.png` is one `\S` run and must yield two spans).

**A lookahead can fire at an offset the token walk never reaches as a boundary, so the extension
lookup owns the token walk.** In `\S+?(?:[^\S\n]+\S+?)*?\.(?:ext)` the lazy group stops at the FIRST
offset where the FOLLOWING lookahead is satisfied — which is frequently in the MIDDLE of what a
whitespace-delimited token scan would treat as one run. Two measured shapes: the extension need
not END the token (`/tmp/a.png[rest]` matches, with the path group at `6..16` and the lookahead
seeing `[` two characters early), and the path group can stop before a character a `\S` scan
includes (`/tmp/a.png。` — the CJK mark is in the lookahead class, so the group ends at the `g`
even though the mark is non-whitespace). So the token scan must be: find the first offset where
the lookahead holds, cut the body there, then test the extension. Walking to whitespace and only
then testing the extension rejects every tag whose terminator is not a space.

**Sibling patterns' lookahead classes differ in MEMBERS, not just in the dot arm** — compare
them character by character before assuming one is a subset of the other. A cleanup class carrying
`[` and a dot arm beside an extension-less class that has neither will disagree on exactly the
inputs that carry those characters, and the disagreement reads as a span bug rather than a class
bug. When two lookaheads over the same keyword exist, print both and diff the character sets once.

## Bisecting a hang (never raise the timeout)

A hanging parity runner is a bug, not slowness. Cheapest ladder, in order:

1. **Split the golden by scenario kind** and run each slice — 2 minutes, names the culprit kind.
2. **Split to one scenario per file**, loop with a 5 s timeout each — names the exact input.
3. **Add `eprintln!` at the top of the suspect loop body** printing cursor and limit. If the
   cursor never changes, it is the re-seek rule; if it changes but the limit does not, it is
   the token guard.
4. **Reproduce in a `#[cfg(test)]` unit** calling the private function directly — a unit test that
   hangs localises it and prints `--nocapture` output, which beats reasoning about a runner.
5. Extract the scanner into a standalone `/tmp/t.rs` and `rustc -O` it with the real table
   inlined. Only when 1–4 all fail.
6. **Expose the span helper as a tiny `#[cfg(test)]`-callable probe binary** that prints each
   stage's answer (masked text, scan end, real spans, deliverable spans, final strip). This
   names which stage diverges in one run instead of one run per hypothesis — worth it once the
   first four steps have not converged.
7. **When the port and the reference disagree by exactly one character, print BOTH sides' offsets
   rather than adjusting either.** A one-character diff on a span is almost never an off-by-one in
   arithmetic; it is two different OFFSETS being used, and editing either number to match moves the
   error rather than fixing it. Print `match`, `group` and `candidate` end for the same input on the
   Python side and pick the one the reference actually reports.

Remove the probe binary, the probe module and the `eprintln!`s before the row is gated —
instrumentation left in the port is noise the next porter pays for.

## Stale-binary discipline beyond mutation runs

A diff that is **byte-identical across an edit that should have changed it** means you are
reading a stale binary, not a stubborn port. Check `stat -c %y` on the source file and the
runner binary before believing a result; when they disagree, `touch` the source and rebuild.

This bites hardest when you edit the *library* and run a thin probe binary — cargo's
`Finished in 0.05s` says nothing about whether the binary you are executing contains your edit.