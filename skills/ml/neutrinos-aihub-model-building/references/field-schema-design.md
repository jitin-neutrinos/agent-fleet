# Field schema design for AI Hub extraction models

Decide this before opening the fields page. Changing a data type later is documented to force
manual re-drawing, and renaming a field after creation is not documented at all.

## The governing question

For each candidate field: **is this value printed in the document, or supplied by a human?**

- **Printed in the document** → String field, or a column of a Table field.
- **Supplied by a human** → String field, full stop. Never a Table column.

A Table field *extracts text that exists where you point it*. It has no mechanism to accept a typed
value. A column for a value that is not written anywhere in the PDF comes back empty every time, or
worse picks up the nearest text and mislabels it.

## Worked example — insurance policy clause extractor

Intended schema was four columns in a Table: `clause_type`, `quoted_wording`, `source_document`,
`page`. Three corrections followed from applying the governing question:

| Intended column | Is it printed in the PDF? | Correct shape |
|---|---|---|
| `clause_type` | No — it is a classification you assign | **String field**, value typed at confirmation |
| `quoted_wording` | Yes — the clause text | Table column (or a one-column Table) |
| `source_document` | No — the filename is not inside the PDF | **Drop it.** Response carries `file_name` |
| `page` | Inconsistently — footers vary across issuers | **Drop it.** Response carries `bbox` per entity |

Final schema — four fields:

| Field | Type | How it gets its value |
|---|---|---|
| `policy-product` | String | Read from the document (footer) |
| `clause-heading` | String | Read from the document (benefit title) |
| `clause-type` | String | **You type it** at confirmation: condition / exclusion / deductible / copay / sublimit / limit / waiting_period / cover |
| `clause-table` | Table | Read from the document, one column, returns N rows per page |

Two fields point at the same region: the Table reads the wording out, the String field is told what
kind of clause it is.

## Do not create fields the response already carries

The extraction response includes `file_name` at the top level and a `bbox` on every entity — the
coordinates of what was read. Source document and on-page location come for free. Creating fields
for them asks the model to find text that is not there.

## Setting a String field

1. Add Field, type the name, leave the data type as String.
2. **Double-click the rendered `String` text next to the field name** — it is the type selector, not
   a label. A single click selects the row; a double-click opens the type options.
3. On the tagging screen: Draw the boundary box, drag over the region, then Apply, then Confirm.
4. For a field whose value you supply, **overwrite whatever the platform proposes at confirmation.**
   It has no basis for that value and accepting its guess teaches the model its own error.

## Field types beyond String and Table

The docs never enumerate the full palette — only String and Table are documented, with the Table
example using No / Description / Net Price / VAT / Gross Worth. Expect to see Number, Date and
similar in the type list; that is undocumented but harmless.

## Multiple sections

The docs only ever describe one — "Add Field under Section One, a predefined and available section".
There is no documented Add Section control. Keep every field in Section One. Nothing is lost: the
feedback loop is per field, not per section. Sections only affect the `section_name` grouping in the
API response.