# 10번 post-cluster Primary 설계와 검증

## 목적과 실행 계약

Primary는 한 기사의 **final EventCluster ∪ Statement**를 같은 축의 raw scalar로 점수화한다. `importance_rank`는 기사 내부 strict 순서의 label에만 사용하고 모델 feature, 절대 회귀값, 확률, 출력 quota로 사용하지 않는다. ABOUT/CAUSES label이나 relation degree도 입력에 없다. Event coreference가 끝난 후에만 실행하며 Event 후보 삭제 gate가 아니다.

8번 final lease는 요청 동안 모든 고유 member state와 final membership index, unique grounded role 요약, typed channel mean/mask 및 conflict mask를 보유한다. `PrimaryScorer`는 각 cluster member를 작은 64차원 gate로 안정적인 segmented softmax 집계하고, unique ACTOR/TARGET/PLACE endpoint 및 trigger/Entity/Time 요약과 기사 context 상호작용을 결합한다. 동일 source member는 final closure에서 하나의 member ID로만 들어간다. 누락 역할은 zero vector와 명시 mask이며 낮은 중요도의 정답으로 해석하지 않는다. Event와 Statement는 다른 adapter를 거친 뒤 기존 공통 `primary_adapter`와 **동일 `shared_scalar`**를 사용한다. cross-kind Gold 비교쌍이 두 adapter의 상대 위치를 학습시킨다.

관계 consumer가 `RELATION`을 release한 뒤 Primary가 `PRIMARY` view를 사용한다. 마지막 release 시 lease의 member/cluster/role tensor 참조를 지운다. loss tensor가 autograd graph를 유지하므로 두 release 뒤에도 backward가 가능함을 테스트했다. serving 결과에는 ID, kind, raw `primary_score`, 진단 status만 남긴다. scalar raw scale은 보정되지 않았고 미학습 fresh weight는 서비스 선택에 쓸 수 없다.

## 순위 target와 계산

기사별 strict pair `rank_i < rank_j`에 `softplus(-(score_i-score_j))`를 적용하고 기사 안에서 평균한다. tie는 `TIE_IGNORE`라서 방향이나 equality loss가 없다. 배치가 있다면 valid strict pair가 있는 기사별 loss를 다시 평균한다. strict pair가 없는 기사는 graph-connected zero와 0 valid pair를 반환한다. 최대 4,096 pair의 deterministic sampler는 cross-kind pair가 있으면 적어도 하나를 남기며 Gold closed-world 순서 이외의 label을 생성하지 않는다. rank gap 1과 rank gap 100은 같은 방향 supervision이다. score에 sigmoid/softmax를 적용하지 않는다.

400개 검증된 기존 train Gold에서 final EventCluster 3,908개와 Statement 6,164개, strict pair 103,114개, tie 56,859개, cross-kind strict pair 44,274개가 확인됐다. engineering50의 대응 수치는 별도 JSON에 있다. 부분 Gold의 이 분포를 전체 1K의 최종 분포라고 간주하지 않는다.

## 논문에서 차용한 부분

| 논문이 다룬 문제 | 이번 목적과 차용 | 가져오지 않은 것·확인할 실험 |
|---|---|---|
| [RankNet](https://www.microsoft.com/en-us/research/publication/learning-to-rank-using-gradient-descent/)은 neural ranking function의 pairwise cost를 연구했다. | article-relative strict pair의 score 차이에 logistic loss를 쓴다. | rank 숫자 회귀, 절대 확률, 서비스 출력 수를 가져오지 않는다. tie/cross-kind와 score 부호를 unit fixture로 확인했다. 실제 순위 품질은 후속 학습 평가 대상이다. |
| [Deep Sets](https://papers.nips.cc/paper/2017/hash/f22e4747da1aa27e363d86d40ff442fe-Abstract.html)는 set 입력의 순열 불변 모델을 연구했다. | final member 순서를 바꿔도 같은 cluster vector가 되도록 segmented aggregation을 사용한다. | 중복 insertion 불변성을 논문에서 자동 보장받았다고 주장하지 않는다. member ID 중복은 closure에서 거부하고 permutation parity를 검사했다. |
| [Attention-based MIL](https://proceedings.mlr.press/v80/ilse18a.html)은 bag label용 attention 집계를 연구했다. | 작은 learned gate로 여러 Event member를 요약한다. | MIL의 bag probability/label과 사람에게 충실한 설명이라는 주장을 가져오지 않는다. gate가 mean보다 좋은지는 후속 본학습 ablation으로 확인해야 한다. |

## 비용과 owner

| 항목 | 크기·수명 |
|---|---|
| `PrimaryScorer` fresh parameter | 961,431개 FP32, 약 3.85 MB. 64차원 member gate 포함. |
| `core.primary_adapter` | 단계 4에 이미 존재한 공통 adapter. 10번에서 두 kind가 같이 사용하며 별도 복사하지 않는다. |
| member/cluster transient feature | 약 `M×256` member state, `C×3×256` unique role, `C×8×256` 기존 typed channel과 small mask. request의 final lease만 보유한다. |
| pair loss 임시값 | 기사당 최대 4,096 scalar 비교. `[C,C,H]` 또는 `[S,C,H]` tensor를 만들지 않는다. |
| backbone·DCE | 기존 selective L8/L10/L12 capture와 단일 공유 DCE를 그대로 사용하며 추가 실행 0회. |

## 검증 한계

synthetic backbone과 검증된 train Gold에서 finite ordinal loss, cross-kind 및 member gate·Event/Statement adapter·공통 scalar·공통 adapter gradient, tie 무시, rank 숫자 단조변환 불변, deterministic sampling, permutation 불변(허용오차 `atol=rtol=1e-5`), singleton/empty/event-only/statement-only, 예측 scalar path, 출력 quota 부재, context interaction, release 후 backward를 확인했다. 실제 pretrained 본학습·optimizer step·품질 평가·서비스 threshold 선택은 수행하지 않았다. 전체 Gold intake의 기존 dev 136 Time schema blocker가 남아 있다.
