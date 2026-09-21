# #34 Frozen-A Proposition Scope Scorer Feasibility v1

Canonical A의 absolute semantic-validity/calibration을 변경하지 않고 별도 relative scope responsibility의 feasibility를 평가했다. Runtime, decoder, release integration은 수행하지 않았다.

## 결론

`SCOPE_SCORER_FEASIBILITY_SUPPORTED=false`; `STRONG_SCOPE_SCORER_SUPPORT=false`; diagnosis `PAIR_ARCHITECTURE_LIMITED`.
Next: `SCOPE_REPRESENTATION_OR_GROUPING_REDESIGN`.

## 사전등록 질문에 대한 답

1. A verifier는 3개 #30 Variant-A selected checkpoint SHA와 parity를 확인했고 전체 parameter를 frozen/eval로 사용했다.
2. trainable module은 PropositionScopeScorer 하나뿐이다.
3. 과거 comparator는 generic top competitor와 validity-hidden 중심 repair였고, 이번 scorer는 strict nested scope-only data와 RAW/DCE boundary·outside·width·containment evidence를 사용하며 A acceptance와 분리된다.
4. Scope-train BOTH Gold support 합계는 **8899** (seed별 [2873, 3014, 3012])이다.
5. Validation BOTH cohort support는 UNDER **1661**, OVER **1661**이다.
6. A baseline UNDER accuracy는 **0.746538**이다.
7. Scope scorer UNDER accuracy/delta는 **0.854907 / +0.108368**이다.
8. A baseline OVER accuracy는 **0.464780**이다.
9. Scope scorer OVER accuracy/delta는 **0.786273 / +0.321493**이다.
10. BOTH macro delta는 **+0.214931**이다.
11. EVENT delta는 **+0.204492**이다.
12. STATEMENT delta는 **+0.225767**이다.
13. A_ALIVE support/delta는 **322 / +0.191859**이다.
14. Validation UNDER_ONLY generalization delta는 **-0.623636**이다.
15. Validation OVER_ONLY generalization delta는 **+0.301205**이다.
16. Validation CORE delta는 **+0.012821**이다.
17. R3/R4/R5 delta는 {'R3_ARGUMENT_SCOPE': -0.111111, 'R4_PREDICATE_SCOPE': 0.25, 'R5_CLAUSE_SCOPE': 0.025641}.
18. #28 six-pair recovery/new regression은 **1 / 9**이다.
19. Control gross pathology는 **True**이다.
20. Pairwise cycle rate는 **0.001337**이다.
21. scope-dev/Validation macro improvement는 **+0.168182 / +0.214931**; transfer gate는 **True**이다.
22. 과거 +0.006289를 명확히 넘어섰는가: **True**.
23. SCOPE_SCORER_FEASIBILITY_SUPPORTED는 **False**이다.
24. STRONG_SCOPE_SCORER_SUPPORT는 **False**이다.
25. 다음 단계는 **SCOPE_REPRESENTATION_OR_GROUPING_REDESIGN**이며, 이번 scorer는 runtime/decoder에 연결하지 않았다.

## 해석 경계

- Scope scorer parameter count: **791,553** (limit 1.5M).
- A verifier logit은 read-only feature/baseline으로만 사용했고 scope score와 합치지 않았다.
- Validation24는 selection에 사용하지 않았고 Round04는 targeted diagnostic이다.
- Component feasibility는 end-to-end graph 성능이나 production readiness를 의미하지 않는다.

## Machine-readable summary

```text
WORK_STATUS=SEMANTIC_PROPOSITION_SCOPE_SCORER_FEASIBILITY_COMPLETE
CANONICAL_A_FROZEN=true
A_VERIFIER_MODIFIED=false
A_CALIBRATION_MODIFIED=false
SCOPE_SCORER_ONLY_TRAINABLE=true
SCOPE_SCORER_PARAMETER_COUNT=791553
PRIMARY_TRAIN_POLICY=BOTH_DIRECTION_ONLY
PAIR_SELECTION=FROZEN_A_HARDEST_TOP1_PER_DIRECTION
TRAIN_BOTH_GOLD_COUNT=8899
A_VALIDATION_UNDER_ACCURACY=0.746538229982
SCOPE_VALIDATION_UNDER_ACCURACY=0.854906682721
UNDER_DELTA=0.108368452739
A_VALIDATION_OVER_ACCURACY=0.464780252860
SCOPE_VALIDATION_OVER_ACCURACY=0.786273329320
OVER_DELTA=0.321493076460
A_VALIDATION_BOTH_MACRO=0.605659241421
SCOPE_VALIDATION_BOTH_MACRO=0.820590006020
BOTH_MACRO_DELTA=0.214930764600
EVENT_DELTA=0.204491725768
STATEMENT_DELTA=0.225766871166
ALIVE_PAIR_SUBSET_DELTA=0.191859197908
VALIDATION_CORE_DELTA=0.012820512821
RUN28_RECOVERY_COUNT=1
RUN28_NEW_REGRESSION_COUNT=9
PAIRWISE_CYCLE_RATE=0.001336888579
OLD_GENERIC_PAIR_COMPARATOR_DELTA=0.006289308176
OLD_GENERIC_PAIR_COMPARATOR_STATUS=NOT_SUPPORTED
SCOPE_SCORER_FEASIBILITY_SUPPORTED=false
STRONG_SCOPE_SCORER_SUPPORT=false
RESPONSIBILITY_SPLIT_FIRST=true
PHYSICAL_DIET_LATER=true
NEXT_EXPERIMENT=SCOPE_REPRESENTATION_OR_GROUPING_REDESIGN
```
