# #31 Semantic Scope Auxiliary Gradient / Module Attribution Audit

No training was performed. The audit used six read-only #30 selected MPS checkpoints and exact fixed cohorts/pairs.

## 결론

`PRIMARY_DIAGNOSIS=NO_CLEAR_GRADIENT_CONFLICT`. Gradient cosine과 hybrid swap은 diagnostic attribution evidence이며 causal proof가 아니다. Hybrid는 joint-trained module의 OOD composition일 수 있다.

## 사전등록 질문에 대한 답

1. B-selected DCE의 actual weighted auxiliary gradient norm 평균은 **0.056663**이고 aux/base-total norm ratio 평균은 **0.063669**이다.
2. DCE under-vs-over median cosine은 **0.263033** (NO_CONFLICT)이다.
3. DCE aux-vs-base-verifier median cosine은 **0.091567** (NO_CONFLICT)이고, aux-vs-base-total은 **0.071920**이다.
4. DCE aux-vs-proposal median cosine은 **0.059622** (NO_CONFLICT)이다.
5. Multi-view projection은 under-vs-over **0.324065**, aux-vs-base-verifier **0.129290**로 둘 다 NO_CONFLICT이다.
6. Validity path는 under-vs-over **0.548644**, aux-vs-base-verifier **0.250733**로 둘 다 NO_CONFLICT이다.
7. Boundary/biaffine path는 under-vs-over **0.369257**, aux-vs-base-verifier **0.102469**로 둘 다 NO_CONFLICT이다.
8. 가장 낮은 median alignment는 **G1_DCE / over_vs_proposal**, median **0.046353**이지만 분류는 **NO_CONFLICT**이므로 strong/weak conflict는 아니다.
9. A→B trajectory divergence share가 가장 큰 group은 **G2_MULTI_VIEW_PROJECTION**이다.
10. DCE B-A divergence norm 평균은 **2.739907**, squared-norm share 평균은 **0.216640**이다.
11. AA Validation exact는 **0.372878682892**, #30 A parity는 **true**이다.
12. BB Validation exact는 **0.336031375070**, #30 B parity는 **true**이다.
13. AB(A trunk+B verifier) Validation exact는 **0.321599467031**이다.
14. BA(B trunk+A verifier) Validation exact는 **0.369562069125**이다.
15. AB-BB exact recovery는 **-0.014431908039**이다.
16. BA-AA exact delta는 **-0.003316613767**이다.
17. Fixed CORE DCE_A+B_verifier(AB)는 **0.397435897436**이다.
18. Fixed CORE DCE_B+A_verifier(BA)는 **0.371794871795**이다.
19. #28 six consensus-correct counts AA/AB/BA/BB는 **{'AA': 1, 'AB': 1, 'BA': 0, 'BB': 1}**이다. AB/BB verifier swap은 AA 대비 각 1개를 회복하고 1개를 잃었으며, BA DCE-trunk swap은 회복 없이 1개를 잃었다.
20. Validation fixed subspan AB/BA effect는 **+0.001551003808 / +0.005916860773**, superspan은 **+0.123363379733 / +0.017806557731**이다. 각 taxonomy에서 절대 effect가 큰 swap이 더 강한 diagnostic attribution을 갖는다.
21. UNDER_ONLY expected auxiliary mass share는 **0.195452**이다.
22. DCE_LEAKAGE_SUPPORTED는 **false**이다.
23. VERIFIER_CONFLICT_SUPPORTED는 **false**이다.
24. COADAPTATION_SUPPORTED는 **false**이다.
25. PRIMARY_DIAGNOSIS는 **NO_CLEAR_GRADIENT_CONFLICT**이다.
26. 다음 실험은 **ONE_TARGETED_FOLLOWUP**이다. AB의 functional damage는 verifier 쪽을 가리키지만 strong gradient conflict가 없어, 현재 증거만으로 BOTH-only verifier-only를 확정하지 않는다.

## 계약 및 한계

- #30 selected checkpoint SHA parity: **true** (6/6).
- Primary gradient statistical unit은 pair가 아니라 article이며 326 BOTH Gold가 있는 모든 article을 사용했다.
- AA-selected fixed structural pair identity를 AA/AB/BA/BB에 공유했다.
- Protected source parity: **true**. Start HEAD: `6b90f8068dd089f5fd11e8c7a1456b8c551157a2`.

## Machine-readable summary

```text
WORK_STATUS=SEMANTIC_SCOPE_AUX_GRADIENT_ATTRIBUTION_AUDIT_COMPLETE
NEW_MODEL_TRAINING=false
OPTIMIZER_STEP_COUNT=0
RUN30_SELECTED_CHECKPOINT_COUNT=6
BOTH_DIRECTION_GOLD_COUNT=326
UNDER_ONLY_GOLD_COUNT=167
OVER_ONLY_GOLD_COUNT=4
DCE_UNDER_OVER_MEDIAN_COSINE=0.263033131054
DCE_AUX_BASE_MEDIAN_COSINE=0.091566530703
DCE_AUX_BASE_TOTAL_MEDIAN_COSINE=0.071919824397
DCE_AUX_PROPOSAL_MEDIAN_COSINE=0.059621625646
MULTIVIEW_UNDER_OVER_MEDIAN_COSINE=0.324064791483
VALIDITY_UNDER_OVER_MEDIAN_COSINE=0.548643542601
BOUNDARY_UNDER_OVER_MEDIAN_COSINE=0.369256850335
STRONGEST_CONFLICT_GROUP=G1_DCE
DCE_BA_DIVERGENCE_NORM=2.739907374598
DCE_BA_DIVERGENCE_SHARE=0.216640451002
AA_VALIDATION_EXACT=0.372878682892
AB_VALIDATION_EXACT=0.321599467031
BA_VALIDATION_EXACT=0.369562069125
BB_VALIDATION_EXACT=0.336031375070
AA_VALIDATION_CORE=0.410256410256
AB_VALIDATION_CORE=0.397435897436
BA_VALIDATION_CORE=0.371794871795
BB_VALIDATION_CORE=0.358974358974
DCE_LEAKAGE_SUPPORTED=false
VERIFIER_CONFLICT_SUPPORTED=false
COADAPTATION_SUPPORTED=false
UNDER_ONLY_AUXILIARY_MASS_SHARE=0.195452143524
PRIMARY_DIAGNOSIS=NO_CLEAR_GRADIENT_CONFLICT
NEXT_EXPERIMENT=ONE_TARGETED_FOLLOWUP
GOLD_MODIFIED=false
MODEL_MODIFIED=false
RUNTIME_MODIFIED=false
RELEASE_MODIFIED=false
```
