# Choosing the model type from the data's shape

Decide this BEFORE opening the wizard, and never carry a model type over from a stakeholder deck.
The five errors this file exists to prevent were all caught by the user at the screen, not by review.

## The decision

Ask one question about the training data: **what is the unit the label attaches to?**

| Data shape | Model type | Why |
|---|---|---|
| One label per whole row | **Prediction — Text** | Docs: "choose the column from the dropdown that contains the target categories". The target column is the label; the row is the unit. |
| A span *inside* running text, several per row | **Extraction — Text** | Docs: "Click the identifier on the right panel. Click the text data on the left panel." Gate is 25 tagged SPANS; governing hyperparameter is `model.ner_text.checkpoint_name`. |
| Fields extracted from a document, including rows from a grid | **Extraction — Document** | 25 files, 25 field confirmations. |
| One label per uploaded file | **Prediction — Document** | ≥2 per category AND ≥25 total. |

**Row-shaped data given to Extraction — Text is the classic miss.** The symptom is unmistakable:
the tagging screen makes words individually clickable, because the interface is hunting for an
entity boundary the data has no opinion about. If every row is already a single atomic assertion,
there is no inner span to find, and the model would learn that an assertion can be any length —
erratic spans at inference on real multi-sentence input.

**Extraction — Text is not "the precise version of Prediction — Text."** It is a different unit of
work. Per-assertion labelling does not imply span tagging; it implies one assertion per row, which
is Prediction.

## Consequence worth stating to the user

Prediction — Text has **no manual tagging step at all** when categories come from the uploaded
data — the docs call the confirmation step "optional... if the categories are detected from the
uploaded training data". Extraction — Text requires 25 hand-tagged spans regardless.

So the right model type is also the cheaper one when the data supports it. State that when you
recommend it; it reframes the change from a setback to an upgrade.

## Per-assertion labels without span tagging

The usual reason people reach for Extraction — Text is a note containing several assertions of
different kinds, and they want each labelled separately. Keep Prediction — Text and move the
splitting upstream: chunk the note deterministically into one assertion per row at inference time,
send each row to the model, reassemble. A deterministic splitter plus a classifier is easier to
audit than a span model, and every assertion gets a label.

## Verify before you build

1. Confirm the wizard path matches the model type you designed for.
2. Confirm the confirmation step's semantics: manual span tagging, or optional row confirmation.
3. If the interface behaves in a way the data does not support, the model type is wrong. Say so
   rather than reinterpreting the data to fit the screen.