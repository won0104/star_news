# V3 Event Identity / Coreference Completion v1

## 결론

Current EventFrame을 기존 EventFeatureBundle의 선택적 current-contract mode로 정확히 migration했다. 모든 요청 channel은 실제 non-zero tensor와 availability mask, Event ID alignment까지 확인됐다. 하지만 selected Event coreference model은 all-KEEP collapse를 벗어났음에도 internal MERGE F1 0.60 gate를 통과하지 못했다. 따라서 canonical runtime/release/graph에는 승격하지 않았고 기존 raw EventFrame과 upstream lanes를 그대로 보존했다.

## 핵심 답변

1. Migration은 PASS다. Historical EventFeatureBundle mode와 checkpoint shape는 유지했고 current mode만 추가했다.
2. Proposition, Trigger, raw ACTOR/TARGET/PLACE, resolved Entity, attached Time, document context가 모두 실제 non-zero tensor로 encoder까지 전달됐다.
3. Frozen masking에서 모든 channel이 prediction을 일부 변경했다. 다만 PR-AUC 기여 방향은 channel마다 달랐고 Time/raw PLACE 제거는 오히려 개선되어, 존재와 유용성을 구분해야 한다.
4. 전체 Curated pair는 MERGE 352, KEEP 23653이며 train split은 MERGE 192, KEEP 15809다.
5. All unordered same-article distinct pair universe의 representable MERGE recall은 1.0이다(모델-unrepresentable Event는 upstream 진단으로 별도 분리).
6. MERGE prediction 205개로 historical all-KEEP collapse는 벗어났다.
7. Internal Gold/Gold-like P/R/F1/PR-AUC는 0.1756/0.2466/0.2051/0.1662다.
8. pilot_dev Gold endpoint+predicted features F1은 0.0000다.
9. pilot_dev fully predicted cascade F1은 0.0000다.
10. Internal cluster B3 F1 0.9053, exact partition rate 0.5000이지만 pair gate 실패로 runtime quality로 승격하지 않았다.
11. False split 125가 false merge 26보다 크다.
12. Fully predicted FIRST LOSS의 가장 큰 항목은 EVENT_UPSTREAM_MISS다.
13. Masking 반응과 proposition-only degradation은 feature 소비를 입증하지만 causal utility를 보장하지 않는다. Proposition/context/raw participant/Trigger 제거는 PR-AUC를 낮췄고, raw Place/Time 제거는 오히려 높였다.
14. 승격하지 않았으므로 새 LocalEvent graph materialization은 실행하지 않았다. 기존 graph replay에서 raw EventFrame은 100% 보존됐다.
15. Assertor는 Event identity의 hard prerequisite가 아니므로 별도 Work Bundle로 넘어갈 수 있다. 이 작업은 Assertor를 시작하지 않는다.

## Architecture 및 supervision

EventCoreferenceHead와 SymmetricPairEncoder 한 family만 사용했다. Pair는 unordered, self-pair 제외, article-local all-pair다. 모든 MERGE를 보존하고 KEEP은 deterministic hard/representative 50:50, 8:1로 제한했다. Synthetic EventCoreference는 사용하지 않았다. Loss는 기존 binary CE이며 effective 1:8 분포에 대한 bounded MERGE weight 4만 사용했다.

## Feature masking

```json
{
  "NO_CONTEXT": {
    "pr_auc_delta": -0.023116161017770892,
    "prediction_change_count": 792
  },
  "NO_PROPOSITION": {
    "pr_auc_delta": -0.03554929273698276,
    "prediction_change_count": 109
  },
  "NO_RAW_ACTOR": {
    "pr_auc_delta": -0.010535840039410493,
    "prediction_change_count": 43
  },
  "NO_RAW_PARTICIPANT": {
    "pr_auc_delta": -0.030715545338216715,
    "prediction_change_count": 88
  },
  "NO_RAW_PLACE": {
    "pr_auc_delta": 0.004980429844404555,
    "prediction_change_count": 10
  },
  "NO_RAW_TARGET": {
    "pr_auc_delta": -0.007848604912564783,
    "prediction_change_count": 80
  },
  "NO_RESOLVED_ENTITY": {
    "pr_auc_delta": -0.0030904175814107093,
    "prediction_change_count": 9
  },
  "NO_TIME": {
    "pr_auc_delta": 0.0393061872873004,
    "prediction_change_count": 318
  },
  "NO_TRIGGER": {
    "pr_auc_delta": -0.01864857535389705,
    "prediction_change_count": 47
  },
  "PROPOSITION_ONLY": {
    "pr_auc_delta": -0.089500602019881,
    "prediction_change_count": 2658
  }
}
```

## 판정

`EVENT_IDENTITY_BLOCKED` — representation wiring과 tiny learnability는 PASS지만 internal F1 promotion gate가 FAIL이다. Release checkpoint, runtime config, graph schema는 변경하지 않았다.
