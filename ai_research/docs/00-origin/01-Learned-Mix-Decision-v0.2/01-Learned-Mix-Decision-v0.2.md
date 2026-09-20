# Learned Mix Decision v0.2

## 결정

L8/L10/L12를 섞는 general layer adapter를 base architecture에 채택하지 않는다. 다음 실험은 dev로 선택한 static task layer를 사용한다.

```text
Entity            L12
Time              L10
Trigger           L8
Sentence Presence L8
```

## 판정 근거

3-seed shallow probe에서 learned mix가 사전 task gate를 통과한 항목은 Entity와 Trigger뿐이었다.

| task | best single | mix dev gain | mix test gain | 판정 |
|---|---|---:|---:|---|
| Entity | L12 | +0.0119 | +0.0163 | PASS |
| Time | L10 | +0.0032 | +0.0086 | FAIL |
| Trigger | L8 | +0.0053 | +0.0034 | PASS |
| Sentence Presence | L8 | +0.0049 | +0.0023 | FAIL |

전체 채택에는 3/4 task 통과가 필요했으나 2/4에 그쳤다. 상세 계약, exact span과 출력은 [DirectionTest 보고서](../../DirectionTest/Report-KF-L8-L10-L12-Learned-Mix-Probe-v1.md)에 있다.

## Architecture 영향

초기 설계의 필수 `task-aware LayerAdapter`를 `static TaskLayerPolicy`로 축소한다.

```text
KF-DeBERTa multi-layer output
  └─ static TaskLayerPolicy
       ├─ SchemaConditionedSpanFamily
       ├─ Sentence Presence + document context
       ├─ DirectedPairFamily        (layer 미정)
       └─ SymmetricCoreferenceFamily(layer 미정)
```

Entity와 Trigger에서 확인된 L8/L12 보완성은 optional ablation으로 보존한다. Label-conditioned scorer가 static single layer에서 먼저 fixed Head를 이긴 경우에만 그 scorer에 learned mix를 추가 비교한다.

## 다음 gate

1. Entity L12, Time L10, Trigger L8에서 fixed task Head와 label-conditioned span scorer 비교
2. Sentence Presence는 L8 + document context로 별도 복원
3. Gold mention을 고정한 directed pair/coreference probe

Static policy는 shallow probe의 다음 기준선이지 production 최종 layer 계약은 아니다. Full shared-context 또는 fine-tuning에서 layer preference가 바뀌면 새 version의 근거 문서로 갱신한다.
