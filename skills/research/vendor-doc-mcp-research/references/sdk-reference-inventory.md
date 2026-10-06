# SDK reference inventory (generated TypeDoc in a docs corpus)

Use when the ask is "what SDK methods / tools does this product expose", and
the corpus is a generated API reference (TypeDoc or similar) dumped into the
vendor docs, plus separate usage guides.

## Step order

1. Fetch the ReadMe / class index. That list is the set of classes and enums.
   Interfaces are request and response shapes, not tools — do not count them
   as methods.
2. Fetch the entry class's properties page. That is the accessor tree
   (`sdk.classification.doc`, `sdk.assistant.knowledge`). A bullet that names
   a property the typed list does not include is not an accessor.
3. For each class you will name, open the methods page the class page links
   to. That TOC is the method inventory. Copy names from the TOC, not from a
   usage-guide table.
4. Fetch a usage guide only to attach HTTP paths, and only for methods already
   on the class TOC. If the guide lists more routes than the class page,
   those extras belong to the low-level `root` service — say so, do not merge
   them into the narrower class.
5. Read one example. If its accessor or method name differs from steps 2–3,
   report both. Do not silently prefer the example.

## Method-count discipline

A total like "68 methods" must be the sum of the per-class TOC lists you
actually enumerated — never a usage guide's aggregate line. Corollary:
method-file mapping in a TypeDoc corpus is positional, not readable off the
filename. `methods-1-2-3.md` looks like an ordinal but its class is lost on
disk (ClickHelp strips the breadcrumb); recover it from the LIVE methods
page's breadcrumb (`» Implementation details » [ConversationService] »
Methods`) or from an unambiguous method name (`ping` → InferenceSDK),
never by assuming file order maps to declaration order — one 2026-10-04
assumption got ClassificationDocService wrong until a live snippet pinned
the actual owner of each methods file.

## Disagreements to expect

- Two import strings in the same corpus (unscoped package vs a scoped name).
  Cite both. Do not guess which one installs.
- Properties page says `assistant.root` / `model.root`; an example calls
  `sdk.assistant.conversation.create` or `sdk.modelCatalog.root`. The signature
  may be `createConversation` while the example calls `create`.
- A usage guide renames a method (`uploadFileToBatch` vs `uploadDocumentToBatch`).
  The class TOC wins for the SDK name; mention the guide's alias.
- Sample hosts in the ReadMe are placeholders, not the live endpoint.

## What not to ship

Do not present these methods as tools the chat harness can call. The docs MCP
searches and fetches pages. Running a method means installing the package and
constructing the entry class.
