# Training Gold 380 (R01–07, R10)

This bundle concatenates the accepted R1–6, R7, and R10 Gold payloads and merges their accepted exact-pair relation sidecars. It creates no semantic decisions, annotations, or inferred negatives.

## Gold

- ARTICLE_COUNT=380
- R1_06_ARTICLE_COUNT=300
- R7_ARTICLE_COUNT=50
- R10_ARTICLE_COUNT=30
- ARTICLE_ID_UNIQUE=true
- SOURCE_PAYLOAD_PARITY=true
- CONTENT_SHA_PRESERVED=true
- OFFSET_EXACT=true
- GOLD_SHA256=0d580a8511cdb191306e1ed786e7aa9f0c5073b608d59a97b8eebd499fd2a649

## Round-07 hard-relation refresh

- R7_HARD_REFRESH_STATUS=PASS
- R7_HARD_PAIR_PARITY_WITH_V1=true
- R7_HARD_V1_EXACT_PAIR_COUNT=90
- R7_HARD_V2_EXACT_PAIR_COUNT=90

## Relation authority

| lane | POSITIVE | SAFE_NEGATIVE_PAIR | UNKNOWN |
| --- | ---: | ---: | ---: |
| ASSERTOR | 3230 | 231 | 36 |
| ABOUT | 1248 | 280 | 56 |
| CAUSES | 303 | 57 | 10 |
| SUBEVENT_OF | 423 | 131 | 4 |

The ASSERTOR sidecar contains one accepted explicit supplemental positive beyond the 3,229 canonical Gold keys. Canonical-positive parity means every canonical positive is present; it does not manufacture or discard accepted source authority.

## Validation

- CANONICAL_POSITIVE_PARITY=true
- DANGLING_ENDPOINT_COUNT=0
- DUPLICATE_PAIR_COUNT=0
- CONFLICTING_PAIR_COUNT=0
- SAFE_POSITIVE_CONFLICT_COUNT=0
- UNKNOWN_TO_NEGATIVE_COUNT=0
- REGEX_GENERATED_NEGATIVE_COUNT=0
- ABSENCE_GENERATED_NEGATIVE_COUNT=0
- GOLD_VALIDATION_STATUS=PASS
- ASSERTOR_ABOUT_VALIDATION_STATUS=PASS
- HARD_RELATION_VALIDATION_STATUS=PASS
- TRAINING_BUNDLE_STATUS=PASS
