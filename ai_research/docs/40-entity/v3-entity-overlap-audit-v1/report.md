# V3 Entity Overlap / Nested Representation Audit v1

## 결과 요약

Round 01–03 최종 adjudicated Gold 150개 전체를 검사했다. Entity mention 4,823개, article-local cluster 1,753개 중 46개 기사에서 overlap 109쌍을 확인했다. 모두 strict nested이며 관련 mention은 213개다.

**flat BIO의 이론적 최소 mention 손실은 104개(2.16%)이고, 현재 pilot의 실제 overlap mask 손실은 정렬된 201개다.** 나머지 overlap mention 12개는 tokenizer exact-end 경계가 없어 tensor 정렬에 실패한다. mask와 정렬 실패를 합쳐 213개를 설명할 수 있지만, 이를 213개 모델 오예측으로 부르면 안 된다. 이번에는 모델 예측/학습을 실행하지 않았다.

현재 mask로 extraction supervision이 영향을 받는 cluster는 133개이고, 그중 모든 mention이 가려지는 cluster는 53개다. 그럼에도 teacher-forced 후보에는 201개 nested mention이 남아 role/assertor positive 102개와 MERGE positive 973개의 tensor supervision을 유지한다. 즉 추출 병목과 downstream conditional 학습 가능성은 별개다.

## 범위·provenance·보호

- commit: `c82dfe0564f93fddccee7510afe205f734507eb7`. prepare 직전 working tree 목록은 `source_manifest.json.initial_git_status`에 있다(이번 새 runner 포함). 기존 변경과 이번 신규 파일의 구분은 `artifact_manifest.json`에 별도로 기록했다.
- 입력은 Round 01 trigger-backfill finalized_batch-r01 및 Round 02/03 finalized_batch다. proposal/reviewer proposal, v2 semantic Gold, 모델 예측은 source로 쓰지 않았다. 모두 원래 1K TRAIN에 속한다.
- 이번 사용자는 Round 01–03 150개 전체를 지정했다. 따라서 그 안에 이미 지정된 pilot_dev/pilot_test에 속하는 Gold도 표현 감사에 포함된다. pilot test 성능/예측은 읽거나 평가하지 않았고, threshold/checkpoint/architecture를 선택하지 않았다. 원래 1K dev/test는 사용하지 않았다.
- 최종 annotation snapshot digest: `dd309396af96704bd5f5249ac0cb488869570b049acd39c75f729f6e44dad4a1`. 세 source 파일 경로·SHA, processed SHA, r01 guideline, tokenizer 파일 SHA는 source manifest에 있다.
- tokenizer는 기존 `363b171d71443b0874b0bf9cea053eb5b1650633` local fast-tokenizer이며 sentence cap128을 그대로 사용했다. Backbone/selected checkpoint는 실행용으로 로드하지 않았다(checkpoint 파일은 보호 SHA만 계산). 기존 registry를 target builder용으로 인스턴스화했으며 모든 Head forward/backward/optimizer step은 0이다.
- semantic necessity는 109쌍을 각각 원문·cluster·direct evidence와 대조한 **AI_DIAGNOSTIC_ONLY**다. 사람 검수나 Gold 재판정이 아니며 confidence는 calibration하지 않았다. 별도 reviewer agent를 사용했다고 기록하지 않았다.

## 중심 실행 경로와 현재 표현 한계

최종 Entity mention → sentence-local adapter view → fast-tokenizer exact alignment → BIO target builder → v3 overlap mask가 Entity 추출 supervision 경로다. 이와 별개로 동일 Gold mention → 후보 span tensor → role/assertor/coreference pair tensor가 teacher-forced 경로다. BIO mask가 이 후보들을 삭제하지 않는다.

1. [원문 mention을 보존하고 overlap을 표시하는 변환기](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/v3_pilot_adapter.py:293)는 Entity mention을 먼저 view에 남기고 겹침에 참여한 모든 span을 coverage.v3_entity_overlap_spans로 기록한다. 4,823개 중 Washington D.C. 한 mention은 sentence 분리로 view에서 제외된다.
2. [단일 BIO 정답을 구성하는 adapter](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/models/tasks/baseline.py:144)는 `[B,S,T]` 정수 target에 원문 mention 순서대로 B/I를 기록한다. 일반 builder만 보면 겹침은 last-write-wins가 될 수 있다. 그러나 pilot은 다음 단계에서 그 중첩 영역을 전부 가리므로 이 덮어쓴 label이 유효 정답으로 학습되지는 않는다.
3. [중첩 토큰을 가리는 pilot collator](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/v3_pilot_collator.py:24)가 각 aligned overlap span 전체를 -100으로 바꾼다. 실제 425개 distinct article/sentence/token 위치가 가려졌고 부분 mask mention은 0, 전체 mask mention은 201개다.
4. [Entity 분류 Head](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/models/spans/entity.py:11)는 `[B,S,T,H]→[B,S,T,9]`; [token CE](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/models/tasks/baseline.py:804)는 -100을 제외하고 유효 token 평균을 계산한다. [BIO decoder](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/models/decoding/spans.py:37)는 token당 argmax 하나와 active span 하나로 flat/non-overlap span을 복원한다. 같은 type nesting도 동시에 표현할 수 없다.
5. [Gold 기반 후보 생성기](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/data/candidate_builder.py:140)와 [후보 표현기](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/models/context.py:115)에는 overlap row 금지 조건이 없다. 실제 packed pair의 source/target index, target value, mask, class mask를 추적해 유효 supervision을 확인했다. gradient/학습 성능을 이번에 검사한 것은 아니다.

## 겹침 분포

모든 span은 processed content의 Unicode code point, 0-based, end-exclusive다. containment는 경계 한쪽을 공유해도 strict nested로 분류하고, 양쪽 동일 경계는 별도 exact same span으로 둔다.

| Boundary relationship | pair 수 |
|---|---:|
| exact same span | 0 |
| strict nested | 109 |
| partial overlap | 0 |
| adjacent/tokenization 대조 사례(109쌍과 별도) | 2 |

두 adjacent 사례는 `전남광주` 내부의 전남/광주로 문자와 exact token 구간이 모두 맞닿을 뿐 겹치지 않는다. 연속 B 태그로 보존 가능하며 overlap 손실에 더하지 않았다. exact 정렬된 mention 사이에서 문자상 비중첩인데 token만 겹치는 pair는 0이다. subtoken 12개는 이 adjacent 분류로 섞지 않고 정렬 실패로 별도 보고한다.

| 관계 | 수 |
|---|---:|
| same type | 68 |
| different type | 41 |
| same cluster | 43 |
| different cluster | 66 |
| unresolved cluster relation | 0 |

cluster relation은 기존 REVIEWED coverage와 cluster ID 배정을 읽은 결과이지 새로운 MERGE/KEEP annotation이 아니다. OP0091의 익명 역 인근은 이름 불명이라는 ambiguity가 있지만 런던 도시 전체와 구체적 역 인근이라는 서로 다른 cluster 배정은 명시돼 있다. ambiguity 원문을 유지했고 이를 확정 장소명으로 바꾸지 않았다.

| Round | articles | overlapping mentions | 최소 flat mention 손실 |
|---|---:|---:|---:|
| 01 | 50 | 92 | 44 |
| 02 | 50 | 74 | 37 |
| 03 | 50 | 47 | 23 |

## Semantic necessity — AI diagnostic, 원본 불변

| diagnostic family | pairs | 해석 |
|---|---:|---|
| 둘 다 독립적으로 필요 | 21 | 사람/소속, 의뢰인/변호인, 실물/모형 등 identity와 semantic 책임이 다름 |
| 긴 mention만으로 의미가 충분해 보임 | 15 | 같은 referent를 긴 span이 이미 지시함. exact evidence 삭제를 승인하는 것은 아님 |
| 짧은 mention도 별도 coref/evidence에 필요 | 4 | 짧은 이름/제목에 실제 role/assertor reference가 연결됨 |
| abbreviation/full-name | 21 | 약칭·공식명·괄호표기; 같은 cluster라도 두 mention boundary는 다름 |
| compositional organization/location | 31 | 국가-기관, 도시-시설, 모회사-소속 조직 등 |
| annotation artifact 의심 | 16 | 브랜드 부분문자열, 조사·따옴표 경계 중복, 복수 PERSON, 잘못된 alias 가능성 |
| ambiguous | 1 | 투어 제목 안 가수 이름의 별도 mention 필요성 |

이 family는 단일 primary 분류이며 배타적인 semantic truth ontology가 아니다. 예를 들어 국가-기관의 구성 구조 역시 두 referent 보존에 유용할 수 있다. artifact 의심은 자동 삭제 대상이 아니며, 긴 mention이 충분하다는 의견으로 단축 role/Entity를 재작성하지 않았다. `overlap_cases.json`의 모든 case에 개별 이유·원문·type·cluster·직접 연결 evidence를 보존했다.

### 의미 차이가 중요한 실제 사례

- OP0005 `로킷헬스케어` / `로킷헬스케어 관계자`: 회사와 발화자 PERSON은 다르다. 관계자에 두 ASSERTED_BY가 있다.
- OP0053 `양기환 백기완노나메기재단 기획이사` / `백기완노나메기재단`: 긴 mention은 assertor, 내부 기관은 ACTOR다.
- OP0047 `가자지구` / `가자지구에서 약 160㎞ 떨어진 해상`: 짧은 지명만 남기면 실제 나포 PLACE가 달라진다.
- OP0071 `스페이스아이(SpaceEye)-T` / `스페이스아이(SpaceEye)-T 모형`: 발사된 위성과 전시된 모형이 별도 TARGET이다.
- OP0055 `린지 본` / `본`: 같은 사람이어도 짧은 span에 따로 ACTOR evidence가 있어 strict mention/evidence 계약이 필요하다.
- OP0032 경기장 `대전 한화생명 볼파크` 내부 `한화`가 `한화 이글스` cluster에 연결됨: 후원사 명칭과 야구팀 identity 혼동 의심을 기록했으나 수정하지 않았다.
- OP0089/90 `정숙-현숙`과 두 개별 사람, OP0097 `한국 근로자들`: 복수 표현을 단일 PERSON으로 다룬 부분은 guideline §11.1과 충돌 소지가 있다. textual ACTOR/TARGET 자체를 삭제하자는 뜻은 아니다.

## flat BIO 손실: 이론적 하한과 현재 mask를 구별

| 측정 범위 | mention 수 | 영향 cluster 수 | 모든 mention이 해당 집합에 속한 cluster 수 |
|---|---:|---:|---:|
| 원문 overlap 참여 집합 | 213 | 136 | 54 |
| 실제 BIO overlap mask 집합 | 201 | 133 | 53 |
| 최대-cardinality flat witness에서 제외된 집합 | 104 | 85 | 37 |
| 전체 alignment 실패 또는 BIO mask 집합 | 287 | 184 | 76 |

최대 비중첩 interval 집합을 종료점 순 greedy로 계산하면 raw 4823개 중 4719개를 선택할 수 있어 **최소 104개는 동시에 표현할 수 없다**. 이는 무가중 mention 수 최적화이며 어떤 semantic mention을 버릴지 결정한 것이 아니다. witness에서 영향받은 cluster 85/전체상실37은 그 deterministic witness의 결과일 뿐 cluster 손실의 최솟값이 아니다. 다른 같은 크기 flat 집합은 다른 cluster를 잃을 수 있다.

정렬 가능한 4,737개만 보면 최소 flat 손실은 92개다. 현재 정책은 그 중 하나를 고르는 대신 overlap 관련 201개를 전부 mask한다. 따라서 201과 이론 하한 104(또는 정렬 subset 92)를 같은 수치로 보고하면 안 된다. 현재 span supervision partition은 4,536 정상 + 201 overlap mask + 86 정렬 실패 = 4,823이다.

'모든 mention이 가려진 cluster'는 그 article-local identity의 extraction 정답 토큰이 없다는 의미다. 모델이 다른 문맥에서 일반화해 예측할 가능성을 배제하지 않으며 실제 predicted KG에서 cluster가 사라졌다는 관측도 아니다. 원본 Entity/cluster는 그대로 남아 있다.

## tokenizer/alignment 진단

전체 정렬 실패 86개는 subtoken/exact endpoint 부재 85개와 `워싱턴 D.C.`의 model sentence 분리 1개다. overlap 관련 12개는 모두 token end 내부에 Gold end가 있어 실패한다. 128 truncation을 해제해 다시 tokenize해도 exact end가 없으므로 상한을 늘리면 해결되는 문제가 아니다.

| Gold endpoint 사례 | 실제 token | 문제 |
|---|---|---|
| 삼성 | 삼성전자 | Gold end가 하나의 token 중간 |
| 천문연 | ##연구원 | 약칭의 마지막 연이 연구원 token 내부 |
| 아이오니스 파마슈티컬스 | ##스는 | 조사까지 묶인 token 때문에 기업명 exact end 부재 |
| 오세훈 서울시장 | ##장이 | 직함 끝과 조사가 동일 token에 들어감 |
| 한국 근로자들 | ##들이 | 복수 접미 표현과 조사의 결합 token |

실제 token index·원문 offset·text, truncation 전후 endpoint 개수를 `downstream_impact.json.unaligned_mentions`에 저장했다. 문자열 첫 출현 find로 다른 mention에 옮기지 않았다. BIO를 다른 token-span Head로 바꾸는 것만으로 이 12개가 회복된다고 계산하지 않는다.

## role / assertor / coreference 영향

직접 영향은 같은 offset의 Entity mention과 role/assertor.entity_id의 cluster가 모두 맞는 evidence만 센다. 단순 포함 관계나 같은 cluster의 다른 mention을 direct loss로 만들지 않는다. TIME attachment는 별도 time_mentions를 참조하므로 직접 Entity-overlap 영향은 0이다.

| raw exact evidence가 overlap mention을 참조 | raw links | 현재 oracle tensor에서 유지 | 다른 이유로 tensor 부재 |
|---|---:|---:|---|
| ACTOR | 38 | 36 | Entity end 정렬 실패 2 |
| TARGET | 21 | 20 | Entity end 정렬 실패 1 |
| PLACE | 13 | 13 | 0 |
| ASSERTED_BY | 34 | 33 | source Statement가 model view에서 제외 1 |

201개 masked mention만을 참조하는 link는 ACTOR36/TARGET20/PLACE13/ASSERTED_BY34 = 103개다. 그중 102개는 Gold teacher forcing에서 target/mask가 유효하다. 따라서 BIO mask 때문에 이 102개 pair label도 이미 제거됐다고 주장하면 틀린다. 다만 실제 runtime에서 해당 Entity가 검출되지 않으면 같은 exact evidence의 attachment 후보를 만들 수 없다는 위험은 남는다. 이는 예측하지 않은 counterfactual이며 실제 누락률이 아니다.

assertor 미유지 사례는 `GNEWS-2bc7791a05506abb32151d81eb23b113`, `r02-2bc7791a-as005`다. 김민지 mention은 정렬되지만 연결 source Statement가 model view에 없다. Entity overlap mask 원인으로 잘못 합산하지 않았다.

raw Entity MERGE pair 전체는 18,144개이며, masked mention을 한쪽 이상 포함하는 pair는 1,022개다. 이 중 실제 oracle positive tensor에는 973개가 남는다. 나머지 49개는 반대쪽 mention의 정렬 문제이며 ID별 endpoint 근거가 저장돼 있다. overlap 관련 실제 sampled KEEP 2,734개도 추적했지만 이는 기존 reviewed-coverage sampler 결과이지 unresolved pair를 이번에 negative로 만든 것이 아니다.

정렬 실패 overlap 12개까지 포함한 전체 213 mention의 노출 범위를 따로 보면 raw MERGE pair 1,063개가 해당하며, oracle tensor 973개 외 90개는 endpoint 정렬 때문에 부재다. 이 집합과 201개 mask-only 집합은 포함 관계이므로 합산하지 않는다.

같은 cluster에 다른 정상 mention이 있어 canonical object가 남더라도 1,022개 exact mention-pair evidence를 자동 복원할 수는 없다. 반대로 mention 일부가 가려졌다는 이유만으로 cluster 전체가 없어진다고 세지도 않았다. 더 넓은 cluster-only potential exposure count는 article별 별도 field이며 direct role loss와 합산하지 않는다.

### 평가 분모 주의

collator `gold_exact_spans/entity`에는 정렬된 4,737개가 남고, mask된 201개도 여기에 포함된다. 반면 정렬 실패 86개는 이 조건부 metadata에서 빠진다. 기존 pilot의 oracle 경로는 이 metadata를 사용하지만, cascaded raw Gold 수집은 원본 entity_mentions를 읽는다. 이번 감사는 raw 4,823개를 분모로 따로 보존했으며 모델 metric을 재평가하지 않았다. 조건부 tensor subset 결과를 raw Gold 전체 성능으로 표현해서는 안 된다.

## 표현 옵션 비교

상세 비교는 [options.md](/Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa/training/results/v3-entity-overlap-audit-v1/options.md)에 있다. A는 현재의 명시적 mask/보류 경로, B는 boundary/span classifier, C는 GlobalPointer류 joint span, D는 layered BIO/multi-label token이다. 모두 미구현·미채택이다. 현재 CandidateSpanEncoder는 nested rows를 이미 받을 수 있으므로 주요 차이는 extraction supervision·proposal/decoder와 candidate 개수에 있다.

최대 겹침 깊이는 2이므로 두 독립 BIO layer로 원문 interval 구조를 배치할 수 있는 계산상 가능성은 있다. 하지만 same-type 68쌍 때문에 'Entity type별 BIO 한 개'만으로 충분하지 않으며, token end 부재 12개는 layer 수와 무관하게 남는다. GlobalPointer라는 이름만으로 이 정렬 계약이 해결되지는 않는다.

새 표현을 고르기 전에 exact mention·canonical object·role evidence의 서로 다른 fidelity 목표와 annotation 의심 queue를 분리해 확인하는 것이 적절하다. 이 진단에서 어느 안도 production에 채택하거나 Gold를 정리하지 않았다.

## 검증 및 재현

`V3PilotCorpus.load`의 content SHA·exact span·cluster membership/reference 검증, 실제 collator/packing index parity, pair label/class mask 검사를 실행했다. 109쌍 모두 AI diagnostic label이 있고 원문 span은 보존됐다. 경계 분류/최대 interval 집합/cluster 계수/실제 저장 tensor 계약 테스트 결과는 `test_results.json`, 보호 SHA는 `validation.json`, 산출물 digest는 `artifact_manifest.json`에 있다.

prepare의 전체 150 article tokenize/target/후보 tensor 감사 구간은 8.92초였다. AI 사례 검토·문서 작성 시간은 포함하지 않는다.

```bash
cd /Users/shinyang-com/Desktop/project-free/ArticleLocal-KG-DeBERTa
conda run --no-capture-output -n model-test-py312 python training/scripts/run_v3_entity_overlap_audit.py finalize
conda run --no-capture-output -n model-test-py312 python -m unittest tests.test_v3_entity_overlap_audit -v
```

원문부터 mechanical audit를 다시 만들 때는 기존 snapshot을 보호하도록 새 output을 사용한다. semantic review는 source digest가 같은 경우에만 결합된다:

```bash
conda run --no-capture-output -n model-test-py312 python training/scripts/run_v3_entity_overlap_audit.py prepare --output training/results/v3-entity-overlap-audit-v1-reproduction
conda run --no-capture-output -n model-test-py312 python training/scripts/run_v3_entity_overlap_audit.py finalize --output training/results/v3-entity-overlap-audit-v1-reproduction
```

필수 산출물: overlap_cases.json / downstream_impact.json / options.md / report.md. 추가 evidence: source_manifest.json / test_results.json / validation.json / artifact_manifest.json. 새 파일만 추가한 runner·semantic-review JSON·tests 외에 기존 tracked 파일 변경은 없다. 결과 디렉터리는 기존 gitignore 규칙을 따른다.

GOLD_MODIFIED=false; GUIDELINE_MODIFIED=false; ENTITY_HEAD_MODIFIED=false; TRAINING_EXECUTED=false; PRODUCTION_MODIFIED=false; CHECKPOINT_MODIFIED=false; ROUND_GENERATION_RESUMED=false; COMMIT_PUSH=false. 완료 후 추가 Gold/실험을 이어가지 않는다.
