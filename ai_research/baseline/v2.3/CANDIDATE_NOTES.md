# Candidate contract and review scope

Step 10 passed only the fixed six Phase C gate. Step 12 has not yet run the
DEV39+Story POC32+long-blocker final 72-input contract, so neither full Gold
quality nor the CPU target is certified. The source Python is copied
byte-identically from the development `runtime/` and `models/` trees. Only
the inherited v2.2 runtime/pipeline config paths are made bundle-local;
checkpoint files are copied without deserialization or resaving. The package
manifest records every mapping and digest. Story, Gold, training and historical
result files are not inference dependencies.

Known v2.2 review items remain open: 45 historical exact Gold losses against
stored v2.1 answers; Time/normalization-related PARTIAL outcomes; large
relation support/evidence lists (including a 1,000-support TARGET relation);
same-coordinate multiple interpretations and containment requiring human
review; and unproved arbitrary tensor liveness beyond the request-owner
census. Bounded routing changes candidate cost and some upstream inventory;
it does not by itself resolve these semantic issues. Evidence is not
arbitrarily truncated to improve bytes or latency.

Step 12 must report budget-exhausted/new partial separately from inherited
Time partial and model errors. An implementation or policy/config/schema/input
hash change after this freeze invalidates the freeze and requires a new
runtime validation identity. A document-only change does not turn this
candidate into a final release. `published=false`.
