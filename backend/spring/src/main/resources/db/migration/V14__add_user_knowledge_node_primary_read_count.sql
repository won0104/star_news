-- 이 Node 가 대표 사건으로 실린 기사를 몇 건 읽었는지.
-- 기사 하나가 COVERS 로 사건 10여 개에 이어지는데, 대부분은 본문에 스치듯 언급된 부차 사건이다.
-- 지금은 기사를 읽으면 그 사건이 전부 "본 것"이 되어 추천 후보에서 빠진다. 한 건을 읽고 사건
-- 열다섯 개가 후보에서 사라지면서, 정작 취향 벡터에는 기여하지 않는다(클릭 0 이라 가중치 0).
-- 대표 사건(COVERS.isPrimary)만 세어 두고 추천에는 그 사건만 소비로 보낸다.
-- 화면(개인 그래프)은 read_article_count 를 그대로 쓰므로 보이는 Node 는 달라지지 않는다.
ALTER TABLE `user_knowledge_nodes`
    ADD COLUMN `primary_read_count` INT UNSIGNED NOT NULL DEFAULT 0 AFTER `read_article_count`;
