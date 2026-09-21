# Models

`ArticleLocalKGModel`은 한 번의 backbone forward와 교체 가능한 component 경계를 조립한다.
`TaskRegistry`의 adapter는 `build_targets / forward / compute_loss / decode / metrics`를
공개하므로 trainer가 Head class나 BIO tensor shape를 알지 않는다.

- Token/span: Entity BIO L12, Time BIO L10, Trigger boundary L8, Semantic two-stage L8
- Shared: L8 document context, candidate span encoder, directed pair encoder,
  `EventFeatureBundle` assembler/encoder
- Separate: Presence/StatementType branches, Assertor/Argument/Relation branches,
  Entity/Event coreference encoders/scorers
- Non-neural: `EligibilityMask`, `TrainingPairSampler`, `RuntimePairPruner`, `decoding/`

`nn.Module` 수는 supervision task 수와 같지 않다. 예를 들어 Sentence Presence의 two-bit와
4-state auxiliary classifier는 하나의 supervision responsibility이고, Semantic은 boundary와
verification 두 module을 가진 하나의 task family다.

Event feature는 semantic/trigger/ACTOR/TARGET/PLACE/TIME/sentence/document를 분리한다.
Oracle one-hot과 predicted Argument weight 모두 같은 assembler를 통과하며 Relation과
EventCoreference는 Gold annotation field를 직접 읽지 않는다.
