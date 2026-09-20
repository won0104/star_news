# V3 표현·gradient·수명 계약 — 단계 4

## 현재 연결된 경로

`ValidatedGoldArticle` → `TargetCompiler`의 `ArticleTargets`는 **학습 target 전용**이다. 동일한 `RawArticle` → `LayoutBuilder` → `SourceWindowBatch.article_view`는 Gold 없이 source tensor를 만든다. 주입된 고정 `KFDeBERTaBackbone`은 `FrozenBackboneFeatureBuilder`에서 `eval`·`no_grad`로 문장 view를 한 번 처리하며 L8/L10/L12 일반 tensor만 반환해야 한다. `V3Core.forward_shared`는 L8을 단일 `DocumentContextEncoder`와 `JointSpanProposalHead`에 전달한다. 이 함수에는 `no_grad`가 없다. 실제 pretrained weight를 load한 forward는 이 단계에서 실행하지 않았고, synthetic `BackboneOutput`으로 finite backward를 확인했다.

단계 4는 `semantic_proposer` 공유 forward와 factory/registry의 경계다. `canonical_span`, `candidate_span`, `primary_adapter`가 fresh 생성되지만 모든 downstream head의 Gold loss·decode·runtime route는 단계 5–10에 남는다. full-model factory는 미구현 task 목록과 함께 실패한다. 임의의 task output을 0이나 상수로 채우지 않는다.

## 소유권과 마지막 consumer

| 객체 / producer | 현재 또는 예정 consumer | 소유·해제 시점 | gradient |
|---|---|---|---|
| `SourceLayout`, `SourceWindowBatch` / tokenizer·collator | backbone 입력, target alignment | article 요청 또는 training batch; PUBLIC에 저장 안 함 | 없음 |
| 선택 L8/L10/L12 / 단일 frozen backbone | DCE, candidate/Time/Entity head | article 요청의 마지막 feature consumer 후 해제 | backbone 없음; 일반 tensor로 downstream 가능 |
| L8 DCE token/sentence/document / 단일 `V3Core.document_context` | proposer, 후보·role·relation projection | `SharedForwardLease`와 후속 작은 handoff; 마지막 loss/backward 또는 inference consumer 후 `close` | v3 fresh DCE에 연결 |
| candidate span / `V3Core.candidate_span` | Entity/Time/Event/Statement downstream | 단계 5–10에서 bounded candidate chunk owner 연결 | fresh projection; 호출 전까지 미검증 |
| Event/Statement/final cluster compact feature / 후속 head | identity, ABOUT, CAUSES, Primary | `CompactRepresentationBundle` 요청 범위; final membership과 feature가 동시에 존재할 때 전달 | 학습 중 detach·`.item()` 금지; hard membership 자체는 비미분 |
| scalar source evidence·ID·score / `ScalarSemanticRecord` | PUBLIC·진단 serializer | tensor owner가 닫힌 뒤 장기 보존 가능 | 없음 |

기존 v2.3-rc2 `models/backbone.py`의 selective L8/L10/L12 capture, all-valid view와 padded-row일 때만 scatter, direct gather는 그대로 둔다. 같은 기사에 다중 task가 있더라도 같은 producer/context의 backbone·DCE를 재사용한다. `runtime/eventframe/features.py`의 서빙 `@torch.inference_mode` provider는 학습 feature builder로 사용하지 않는다. `FrozenBackboneFeatureBuilder`는 inference tensor를 받으면 실패한다. 공유 DCE는 **이번 v3 run의 단일 owner**이며 과거 서로 다른 checkpoint의 DCE를 묵시적으로 합치지 않는다.

## 표현 identity와 cache

`RepresentationProvenance`는 article version/content SHA, 고정 backbone weight SHA, v3 run/config/revision, layer/mix, context ID, dtype, tokenizer SHA, source layout policy를 갖는다. `CompactRepresentationBundle`은 ordered IDs와 bool mask가 tensor 첫 축과 맞는지 검사하고, consumer가 요구한 producer metadata/ID 순서가 다르면 실패한다. bundle은 context manager 또는 `close()`로 tensor 참조를 지운다. 다른 closure/alias가 보유한 참조까지 해제했다고 주장하지 않는다. semantic carrier serializer `public_scalar_projection`은 tensor, bundle, target batch 등 scalar 외 객체를 거절한다.

`FrozenSourceViewKey`는 source bytes·article version·tokenizer·backbone producer·ordered window/view·input/masks/offsets/dtype을 구별한다. 아직 실제 disk/process cache를 생성하지 않았다. `TrainableViewKey`는 추가로 같은 v3 run, config, model revision, optimizer step, mode, context/mix를 요구한다. `train` mode는 dropout 호출마다 별도 `call_id`가 필수이며 이 단계에서 trainable activation을 cache하지 않는다. `eval` mode도 실제 cache 연결 전 producer와 model revision 검증이 필요하다. 형상이 같다는 이유로 다른 DCE 또는 EventFeatureEncoder를 대체하지 않는다.

## 학습 순서와 provenance

`task_contract.py`의 dependency DAG는 extraction → entity/role/time/attribution → identity → cluster consumers 순서다. `register_task`는 동일 run ID와 upstream 준비 상태, `nn.Module` 구현, parameter alias 부재를 검사한다. 현재 준비된 task는 `semantic_proposer` 하나다. 등록 API의 run ID는 내부 요청의 계약이며 외부 checkpoint provenance를 암호학적으로 증명하지 않는다. 실제 save/reload 및 모든 head의 source 검사는 단계 13의 책임이다.

`V3ArchitectureFactory.fresh_core`는 task checkpoint를 읽지 않고 RNG fork에서 DCE, proposer, canonical verifier/boundary, candidate projection, Primary adapter를 새로 초기화한다. `initialization-manifest.json`은 생성된 모든 parameter의 owner·shape·dtype·digest, 고정 backbone identity, 미구현 task 목록을 기록한다. weight 파일을 생성하지 않는다. 생성되지 않은 downstream head는 `FRESH_INIT`으로 거짓 표기하지 않는다.

## 남은 검증 경계

- 단계 2의 dev Gold 오류 때문에 전체 Gold intake는 `BLOCKED`; 이 단계의 forward/backward는 합성 Gold fixture의 source tensor와 synthetic backbone 출력만 사용했다. 기존 train Gold 400기사는 단계 3 compiler census에만 사용했다.
- Step 3 compiler의 signed boundary·cross-window span을 현재 extraction head가 학습·복원한다는 증거는 없다. 단계 5에서 구현·loss 검증이 필요하다.
- 단계 5–10의 task-specific loss/gradient, final-cluster sparse aggregation, Event/Statement last-consumer 호출 수·실제 RSS/latency는 아직 측정하지 않았다. dense `[cluster,event,hidden]` 또는 full `[E,E,H]` materialization을 후속 경로에 추가하지 않는다.
- 본학습, checkpoint 선택, 서비스 threshold, 원격 게시, DB 쓰기는 실행하지 않았다.
