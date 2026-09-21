-- 본문 해시. 같은 본문이 다른 제목으로 다시 들어오는지 저장 전에 보려고 둔다.
-- 전처리의 본문 중복 검사는 한 수집 회차 안에서만 비교해서, 회차가 다르면 걸러지지 않았다.
-- 실제로 "[뉴스핌 베스트 기사]" 목록 페이지가 서로 다른 제목 8건으로 저장됐다.
ALTER TABLE `articles`
    ADD COLUMN `content_hash` BINARY(32) NULL AFTER `content_type`;

-- 저장 직전에 같은 본문을 찾는 조회에 쓴다. 유니크는 아니다.
-- 통신사 기사를 여러 매체가 같은 제목으로 실은 경우는 정상이라 그대로 저장한다.
CREATE INDEX `idx_articles_content_hash` ON `articles` (`content_hash`);

UPDATE `articles` SET `content_hash` = UNHEX(SHA2(`content`, 256)) WHERE `content_hash` IS NULL;
