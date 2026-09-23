-- GNews가 일부 KBS 기사에서 source.name을 "news.kbs.co.kr"로 보내 제목 보정을 놓쳤다.
-- 아직 분석·요약을 시작하지 않은 기사만 같은 형태로 보정한다.
CREATE TEMPORARY TABLE `kbs_title_repair_targets` (
    `article_id` BIGINT NOT NULL,
    CONSTRAINT `pk_kbs_title_repair_targets` PRIMARY KEY (`article_id`)
);

INSERT INTO `kbs_title_repair_targets` (`article_id`)
SELECT a.`article_id`
FROM `articles` a
JOIN `news_organizations` o
  ON o.`organization_id` = a.`organization_id`
WHERE o.`domain` = 'news.kbs.co.kr'
  AND REPLACE(a.`title`, ' ', '') = 'KBS뉴스'
  AND a.`analysis_status` = 'PROCESSING'
  AND a.`analysis_attempts` = 0
  AND a.`node_id` IS NULL
  AND a.`summary_status` = 'NOT_REQUESTED'
  AND a.`summary` IS NULL
  AND SUBSTRING(
        REPLACE(a.`content`, '\r\n', '\n'),
        CHAR_LENGTH(SUBSTRING_INDEX(REPLACE(a.`content`, '\r\n', '\n'), '\n', 1)) + 2
      ) LIKE '읽어주기 기능은 크롬기반의\n브라우저에서만 사용하실 수 있습니다.\n%';

-- 본문 첫 줄이 실제 제목이다. 제목으로 옮긴 뒤 본문에서는 제거한다.
UPDATE `articles` a
JOIN `kbs_title_repair_targets` t
  ON t.`article_id` = a.`article_id`
SET a.`title` = SUBSTRING_INDEX(REPLACE(a.`content`, '\r\n', '\n'), '\n', 1),
    a.`content` = SUBSTRING(
        REPLACE(a.`content`, '\r\n', '\n'),
        CHAR_LENGTH(SUBSTRING_INDEX(REPLACE(a.`content`, '\r\n', '\n'), '\n', 1)) + 2
    );

-- 제목 바로 뒤에 붙은 KBS 읽어주기 안내를 제거한다.
UPDATE `articles` a
JOIN `kbs_title_repair_targets` t
  ON t.`article_id` = a.`article_id`
SET a.`content` = SUBSTRING(
        a.`content`,
        CHAR_LENGTH('읽어주기 기능은 크롬기반의\n브라우저에서만 사용하실 수 있습니다.\n') + 1
    )
WHERE a.`content` LIKE '읽어주기 기능은 크롬기반의\n브라우저에서만 사용하실 수 있습니다.\n%';

-- 기사 하단의 KBS 제보·반응 블록은 표지부터 버린다.
UPDATE `articles` a
JOIN `kbs_title_repair_targets` t
  ON t.`article_id` = a.`article_id`
SET a.`content` = SUBSTRING_INDEX(a.`content`, '\n■ 제보하기', 1)
WHERE a.`content` LIKE '%\n■ 제보하기%';

UPDATE `articles` a
JOIN `kbs_title_repair_targets` t
  ON t.`article_id` = a.`article_id`
SET a.`content` = SUBSTRING_INDEX(a.`content`, '\n이 기사가 좋으셨다면', 1)
WHERE a.`content` LIKE '%\n이 기사가 좋으셨다면%';

-- 본문이 바뀌었으므로 중복 판별 해시와 본문 수정 시각도 함께 맞춘다.
UPDATE `articles` a
JOIN `kbs_title_repair_targets` t
  ON t.`article_id` = a.`article_id`
SET a.`content_hash` = UNHEX(SHA2(a.`content`, 256)),
    a.`content_updated_at` = CURRENT_TIMESTAMP(6);

DROP TEMPORARY TABLE `kbs_title_repair_targets`;
