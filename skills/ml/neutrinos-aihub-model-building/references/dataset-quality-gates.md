# Dataset quality gates for rule-derived labels

Applies whenever labels come from deterministic rules rather than from the source dataset.
Real text with invented labels is still invented data, and it fails the same way.

## Ship the rules, not just the labels

Every rule file ships next to the data in plain text, with the pattern strings and the label logic.
Two reasons: an auditor can trace any label back to the rule that produced it, and when a rule is
wrong the fix is a one-line edit rather than a re-derivation.

## Gate 1 — reject the null class

A fallback bucket for "no pattern matched" is not a label. It becomes the largest class, it means
nothing to a reader, and the model learns to invent a category that does not exist in the business.

Drop those rows. If they later prove to be a real category, define the rule that identifies them.

## Gate 2 — context words are not opinion words

High-frequency domain words fire on factual reports:

- "Fraud Department called me" — a completed action, a fact.
- "A fraudulent alias on my file" — an observable record state, a fact.
- "They committed fraud" — an accusation, an opinion.

Requiring the word to be *predicated of a party as an accusation* ("committed", "is a", "they are")
separates them. Count how many labels each candidate trigger alone would flip before shipping it —
a single trigger flipping hundreds of rows is a rule bug, not a class.

## Gate 3 — the label distribution must look plausible

Read the counts before shipping. A corpus where one class holds 90%+ is a model that answers that
class to everything. A corpus where 37% sits in an undefined bucket is Gate 1 failing.

Then **read samples from every class.** Counts do not catch a rule that is consistently wrong in a
way that looks reasonable; reading does.

## Gate 4 — oversample thinly, never flat-target it

Weighting a thin minority class up is correct. A flat per-class target is wrong when classes differ
in natural size by orders of magnitude — it forces a 7x multiplier on the smallest class, which
risks memorising those rows instead of learning the pattern, and floods the set with duplicates.

Cap every minority class at roughly 2x its natural size, and cap the dominant class at a small
multiple of the largest minority. Then:

- Report the duplicate-row count as a headline number, not a footnote. Duplicates add weight, not
  information, and the reader needs to know how much of the set that is.
- Name the class that remains thinnest after rebalancing, and say which business risk that class
  covers. The thinnest class is often the commercially most important one.

## Gate 5 — ship a calibration slice

Emit a stratified review file alongside the training set — a few dozen rows per class — for the
user to check against the rules. Every rule-derived label set has a known error rate; the file is
how the user learns it without reading thousands of rows, and it is the only honest way to describe
a rule-derived set to a stakeholder.

## Domain fit is separate from label quality

Say both limits plainly and separately. A set can have excellent labels for the wrong domain, and
"well-labelled financial-services complaints" is not "well-labelled insurance complaints". Never let
a quality gate imply the domain question is settled.