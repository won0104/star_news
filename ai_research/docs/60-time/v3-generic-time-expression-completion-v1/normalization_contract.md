# Generic TimeExpression normalization contract

## Responsibility

Normalization belongs to ⑧ Graph Assembly. It is a deterministic, evidence-preserving
projection over an already predicted `TimeExpression`; it is not a neural subtype
classifier and is not an input feature for ③ extraction or ⑤ attachment.

## Reference policy

- Absolute expressions are normalized without a reference timestamp when a supported
  rule can determine the value.
- Relative expressions may use only the source article's `publishedAt` value.
- The system clock, file timestamp, inference time, web lookup, and LLM inference are
  forbidden normalization references.
- When `publishedAt` is required but missing or invalid, the result is `UNRESOLVED`.
- The emitted provenance records the rule, normalized granularity, reference value, and
  timezone when a reference was used.

## Evidence preservation

Every prediction retains its original text, absolute character offsets, token offsets,
score, prediction ID, and checkpoint provenance regardless of normalization status.
Unsupported, ambiguous, duration-like, set-like, or context-dependent expressions are
valid `UNRESOLVED` evidence. They are never discarded or coerced into a calendar value.

Graph materialization requires both a predicted Event→TimeExpression attachment and a
materializable normalization result. An unresolved or unattached expression remains in
the raw evidence collection and cannot independently create a canonical `TIME` node or
`OCCURRED_ON` edge.

## Supported bounded rules

The v1 runtime supports conservative forms for absolute year/month/day values and a
small bounded set of article-relative day/year/month expressions. It intentionally does
not claim broad Korean temporal parsing coverage. Duration and recurring/set semantics
remain unresolved until their contracts are separately defined.

## Validation limitation

Curated RC exposes normalized Gold for only 8 of 786 reviewed TimeExpression rows
(1.02%). Seven absolute examples matched exactly. One relative example, `이듬해 9월`,
did not: the Curated normalized value reflects historical narrative context while the
processed article's `publishedAt` points to 2026. This is a provenance/reference
conflict, not evidence that arbitrary context recovery is safe. The v1 runtime therefore
keeps the explicit article-relative policy and reports `ACTIVE_WITH_LIMITATIONS`.
