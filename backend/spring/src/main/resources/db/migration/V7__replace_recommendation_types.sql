-- 추천 유형이 근거(INTEREST_BASED·KNOWLEDGE_GAP)에서 계산 방식(NORMAL·COLD_START)으로 바뀌었다.
-- 옛 유형 행은 애플리케이션이 enum 으로 읽지 못해 그 사용자의 추천 보드 조회가 실패한다.
--
-- 새 유형으로 바꾸지 않고 지운다. 두 옛 유형을 하나로 합치면 같은 사용자·같은 회차에 둘로 나뉘어
-- 있던 행이 (user_id, available_at, recommendation_type, rank) 유니크 제약에 걸린다.
-- 추천은 하루 두 번 새로 계산되므로 다음 회차에 다시 채워진다.
DELETE FROM `user_recommendations`
WHERE `recommendation_type` IN ('INTEREST_BASED', 'KNOWLEDGE_GAP');
