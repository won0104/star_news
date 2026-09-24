-- Topic별 탐색 화면에 공개할 Event 진입 Node를 회차별로 저장한다.
-- 조회 요청은 Neo4j를 다시 조회하지 않고 이 테이블의 최신 공개 회차만 읽는다.
CREATE TABLE `topic_exploration_entries` (
    `topic_exploration_entry_id` BIGINT NOT NULL AUTO_INCREMENT,
    `snapshot_at` DATETIME(6) NOT NULL,
    `topic_code` VARCHAR(32) NOT NULL,
    `node_type` VARCHAR(32) NOT NULL,
    `node_id` CHAR(36) NOT NULL,
    `node_title` VARCHAR(500) NOT NULL,
    `rank` INT UNSIGNED NOT NULL,
    `article_count` INT UNSIGNED NOT NULL DEFAULT 0,
    CONSTRAINT `pk_topic_exploration_entries`
        PRIMARY KEY (`topic_exploration_entry_id`),
    CONSTRAINT `uk_topic_exploration_entries_snapshot_topic_node`
        UNIQUE (`snapshot_at`, `topic_code`, `node_type`, `node_id`),
    CONSTRAINT `uk_topic_exploration_entries_snapshot_topic_rank`
        UNIQUE (`snapshot_at`, `topic_code`, `rank`),
    CONSTRAINT `ck_topic_exploration_entries_rank`
        CHECK (`rank` >= 1)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Topic별 탐색 진입 Event 공개 회차';

CREATE INDEX `idx_topic_exploration_entries_topic_snapshot`
    ON `topic_exploration_entries` (`topic_code`, `snapshot_at` DESC);
