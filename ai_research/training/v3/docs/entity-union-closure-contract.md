# 6번 Entity 후보 통합·동일성·endpoint 계약

> Historical contract. The active unified Native/ROLE mention and single
> coreference closure path is [unified-entity-identity-v1.md](unified-entity-identity-v1.md).
> The `role_entity` decision and Entity 128 budget below are not active there.

## 실행 경로와 출처

5번 `DecodedSourceSpan`의 Entity와 Event-conditioned ACTOR/TARGET/PLACE span은 각각 `evidence_from_entity_decode`와 `evidence_from_role_decode`로 exact 원문 좌표를 가진 scalar evidence가 된다. Assertor는 9번 producer가 연결되기 전이며 `ASSERTOR` 입력 계약과 SPAN_ONLY fixture만 구현했다. `build_entity_candidates`는 `RawArticle`과 evidence만 받고 Gold를 읽지 않는다. 먼저 동일 좌표·호환 type·문맥 hint의 중복을 합치고 모든 evidence ID와 origin을 보존한다. 서로 다른 타입·hint는 별도 후보로 남겨 학습된 coreference 결정에 맡긴다. surface 문자열만으로 alias를 합치지 않는다.

역할 근거 후보는 NER 전용 후보보다 먼저 128개 임시 후보 예산을 받는다. ACTOR/TARGET이 확정됐고 기존 4타입이 없으면 제한된 `GENERIC` 후보를 만든다. 불확실한 `PROPOSED` role은 `GENERIC`으로 강제 승격하지 않는다. 예산이 필수 role 후보보다 작으면 `BOUNDED_PARTIAL`과 탈락 수·`PARTIAL_BUDGET` binding을 반환한다. 기존 v2.3-rc2의 `PRIMARY`/`RESCUE_ONLY`는 기존 서빙 경로의 NER boundary family 정책이다. v3의 role origin 예약은 그보다 앞선 별도 candidate universe 계약이며, 현재 rc2 서빙 entry point에는 연결되지 않았다. 따라서 rc2의 NER-only hard conflict 또는 global routing 결과를 v3 필수 role 후보의 최종 폐기 판단으로 사용하지 않는다.

`score_and_close_entity`는 **예측 경로**에서 기존 128-token sentence/bridge windows와 같은 단일 backbone·공유 DCE lease를 받아 source-aligned candidate state를 직접 모은다. 5타입 typing, candidate priority, 대칭 coreference, 방향 role→Entity head를 bounded/chunked pair로 점수화한다. ACTOR/TARGET는 기존 argmax 계약을 유지한다. PLACE는 동일 좌표 NER가 없어도 `PROPOSED` 후보로 진입하고, `role_entity` 최고 logit이 `ServingBudget.place_role_entity_threshold` 이상일 때만 endpoint를 수락한다. 기본값 `0.0`은 미학습 진단용 정책이며 서비스 threshold가 아니다. 거절한 PLACE evidence는 최종 active evidence 집합에서 빠져 role-only fake node를 다시 만들지 않고 `UNRESOLVED_REFERENTIAL`과 scalar 사유를 남긴다. 명시적 `SPAN_ONLY` PLACE/Assertor는 후보로 승격하지 않는다. candidate에는 모델 문맥 ID `CTX:`만 허용하고 Gold Entity ID는 입력에서 거부한다.

`close_entity_identity`는 명시적 pair decision의 complete-link 합류로 article-local Entity ID, 대표 exact grounding, type, observed mention types, candidate/evidence→identity remap과 각 role별 endpoint를 만든다. cluster membership과 final type을 먼저 확정한 다음 대표 source mention을 고른다. exact allowlist의 순수 대명사·지시대명사보다 명시 mention을 우선하고, 명시 mention끼리는 final type 일치 → source order → span/candidate ID 순으로 결정한다. `이 회사`, `해당 기업`처럼 명사를 포함한 표현은 대명사로 일반화하지 않는다. 길이, candidate raw score, `entity_priority`, role/coreference score는 대표 선정 기준이 아니다. 모든 member가 대명사이면 같은 source-order fallback을 사용하며 새 이름을 생성하지 않는다. 서로 다른 Event가 하나의 Entity를 참조해도 role binding 둘은 남는다. 같은 Gold cluster에 서로 다른 mention type이 있는 경우 local type은 `null`, `observed_types`는 모두 남기고 `RESOLVED_TYPE_CONFLICT` endpoint에는 local ID를 유지한다. type 충돌이 근거 없는 entity merge를 허용하는 것은 아니다. 구조적 role 후보가 없는 예측 결과는 fake Entity를 만들지 않고 partial status를 남긴다. 대표 변경은 `representative_candidate_id/start/end/text`만 바꾸며 member inventory 기반 `local_id`, membership, remap, endpoint, final type을 바꾸지 않는다. 반환 객체는 scalar·ID·근거만 가지며 tensor는 live lease 종료 시 해제된다.

## 학습과 재현 범위

`build_oracle_entity_structure`는 **검증된 기존 train Gold 전용**이다. Gold Entity ID는 학습 pair target과 oracle endpoint 검사 안에서만 쓰며 runtime local ID가 아니다. Gold ACTOR/TARGET에 null endpoint가 있으면 즉시 실패한다. EntityMention origin과 role origin을 함께 넣어 typing CE, 후보 유지 양성 loss, 같은 Gold cluster의 unordered coreference 양성 및 결정적 표본 음성, resolved role×Entity cluster 양성 및 허용된 표본 음성으로 gradient를 fresh head와 공유 표현에 보낸다. PLACE/Assertor의 null은 source 증거로 남지만 resolution 음성이 아니다. Gold positive 후보와 pair를 128 후보 cap 때문에 잘라내지 않는다. priority는 현재 양성만 감독하므로 실제 NER 후보 억제·calibration 근거가 없다.

`entity-union-coverage-report.json`의 engineering50은 기존 train 50기사에서 oracle 후보 2,308개(공유 NER+role 1,063, NER-only 1,244, role-only 1), Gold ACTOR/TARGET endpoint 1,187/1,187, SPAN_ONLY 52개, 128 후보 cap의 낙관적 구조 탈락 0개다. 별도 전체 valid train 400기사 oracle 검사는 ACTOR/TARGET 6,307개를 모두 local endpoint로 보존했고, mixed mention type endpoint 3개는 `RESOLVED_TYPE_CONFLICT`로 표시했다. 이 수치는 Gold 주입 구조 감사이며 predicted candidate recall·coreference 품질·서비스 threshold 평가가 아니다. 기존 dev/test Gold는 사용하지 않았다. 단계 2의 dev Gold 오류로 전체 Gold readiness는 계속 `BLOCKED`다.

`entity-initialization-manifest.json`은 fresh parameter 6,517,653개와 준비된 task 11개·미구현 8개를 기록한다. weight 파일은 없다. 실제 pretrained checkpoint, optimizer step, tiny-fit, 본학습, 원격 게시, DB 쓰기는 수행하지 않았다.
