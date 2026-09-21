# ⑧ 그래프 조립부 입력 계약

⑧은 `ArticleLocalRuntimeResult.to_dict()`만 소비해야 하며 experiment 내부 모델·candidate·Gold에 접근하면 안 된다. 현재 available evidence는 final Event/Statement proposition, Event별 raw ACTOR/TARGET/PLACE, exact offsets, scores, checkpoint/config provenance다. Entity mention, generic TimeExpression, Trigger, StatementType, Assertor, narrow ABOUT, resolution, coreference, CAUSES/SUBEVENT_OF는 `NOT_RUN`이다.

따라서 다음 단계는 evidence-preserving partial graph를 만들 수 있지만, 보류 lane을 빈 semantic negative로 해석하거나 완전한 KG라고 주장하면 안 된다. raw participant는 Entity resolution 실패와 무관하게 보존하고 SPAN_ONLY-like raw evidence를 정상 endpoint evidence로 취급한다. generic TimeExpression과 normalized occurrence time은 별도다. MIX는 sentence state이며 node type이 아니다. ABOUT endpoint는 실행 시 Event|Statement만 허용한다. provenance 없는 edge는 materialize하지 않는다.
