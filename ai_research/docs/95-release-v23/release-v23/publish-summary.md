# ArticleLocal KG v2.3 Hugging Face publication

Status: **COMPLETE_V23_HUGGINGFACE_PUBLISH**

The Step 12 validated `v2.3-rc2` package was published to
[`sysy9292/kf-deberta-base-kg-extractor`](https://huggingface.co/sysy9292/kf-deberta-base-kg-extractor)
without rebuilding or modifying the local package.

- Published at: `2026-09-16T08:59:57+00:00`
- Validated package tree SHA-256: `0214782141eef30d3b57a8b74aaca812788b0f644cfad14c59208b507787eb8b`
- Package manifest SHA-256: `42969579d7c6f6e89113a80f582f9442b8e0e09a795d0ea89f484c87ad639995`
- Exact runtime commit: `e962f8e18f12bc8bd94ba664cc5fde64cb408c61`
- Exact runtime tag: `v2.3-validated-runtime`
- README-only model-card commit and final main: `96473a9b437c303a10b2dedf3d7280f0832aa396`
- Final release tag: `v2.3`
- README SHA-256: `65dae8cdfa9c4ff2ed49a410ac047e108516822a453c2344bc1a584b3da76f43`
- README-excluded runtime payload SHA-256: `f73aea7684f18f5467d1dce75a20c5e327b66b5ba1693ba2e3903862d8c2ee89`

Commit A contains the exact 154-file RC2 inventory, including all twelve
checkpoint byte identities. Commit B changes only `README.md`; its remaining
runtime, checkpoint, config, schema, and manifest payload is identical to
Commit A and the validated local RC2. The publish step performed no model load,
article inference, training, package rebuild, or new validation.

Step 12 remains immutable history: it ended with `publish_ready=true`,
`published=false`, and `remote_publish_performed=false`. The subsequent publish
event is recorded in
[`publication-record.json`](../../validation-bounded-candidates/final-v23/publication-record.json).
