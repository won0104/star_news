# v2.3 final validation summary

v2.3 adds bounded Participant→Entity and Event→Time routing, bounded Entity and
Time span candidates, bounded Event pair selection, selective L8/L10/L12
backbone retention, an all-valid view path, and homogeneous/heterogeneous
CandidateSpan gathers. The runtime continues to use FP32, the existing task
checkpoints and thresholds, PUBLIC schema `articlelocal-kg-public-v2.2`, and
output profile `ASSEMBLY_OUTPUT_PROFILE_V3 / PUBLIC`.

The exact `v2.3-rc2` package tree SHA-256 is
`0214782141eef30d3b57a8b74aaca812788b0f644cfad14c59208b507787eb8b`.
Its source mapping, checkpoint bytes, policy/config/schema, isolated import, and
pre/post-execution integrity passed.

The final one-worker CPU/FP32 run processed 72 fixed articles: DEV39 39, Story
POC32 32, and one long blocker. PUBLIC, sidecar, profile, and article-record
counts were 72 each. Grounding/endpoint validation and request-owner census
passed 72/72; ERROR outputs, routing budget violations, global-ALL fallbacks,
OOMs, and structural violations were zero.

DEV39 exact F1 was 0.435993 EVENT, 0.473605 STATEMENT, and 0.419871 ENTITY.
Existing Gold TP retention was 1.0 for all three lanes. The measured70 CPU
average was 3.534950 seconds, P95 6.835772 seconds, and blocker 87.223051
seconds. Process peak RSS was 6,946,750,464 bytes, below the frozen v2.2
reference of 7,313,080,320 bytes.

The result is `COMPLETE_V23_FINAL_VALIDATION_PASS_PUBLISH_READY`.
`publish_ready=true`, while `published=false` and
`remote_publish_performed=false`. Publishing must use the exact validated RC2
contents without post-validation modification.
