-- 개인 그래프 요약(getSummary)이 Topic 별로 상위 N개를 뽑을 때, user_id 로만 좁힌 뒤
-- topic_code·node_type 은 비인덱스 필터로 걸러내던 문제를 고친다.
-- (user_id, topic_code, node_type) 복합 인덱스로 Topic 단위 조회를 바로 좁혀 들어가게 한다.

CREATE INDEX `idx_user_knowledge_nodes_user_topic_type`
    ON `user_knowledge_nodes` (`user_id`, `topic_code`, `node_type`);
