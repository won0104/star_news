-- 별빛 뉴스 MySQL 8.4 LTS 초기 스키마
-- 기준: 최종 DB/ERD 설계 문서
-- 주의: 실행 전 대상 데이터베이스를 선택해야 한다.
-- 모든 DATETIME(6) 값은 KST(UTC+9)를 기준으로 저장한다.

SET NAMES utf8mb4;
SET time_zone = '+09:00';

CREATE TABLE `users` (
    `user_id` BIGINT NOT NULL AUTO_INCREMENT,
    `login_id` VARCHAR(50) NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `nickname` VARCHAR(50) NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    `deleted_at` DATETIME(6) NULL,
    CONSTRAINT `pk_users` PRIMARY KEY (`user_id`),
    CONSTRAINT `uk_users_login_id` UNIQUE (`login_id`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자';

CREATE TABLE `user_interest` (
    `user_id` BIGINT NOT NULL,
    `topic_code` VARCHAR(32) NOT NULL,
    `interest_type` VARCHAR(20) NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `pk_user_interest` PRIMARY KEY (`user_id`, `topic_code`),
    CONSTRAINT `fk_user_interest_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자 선호 및 비선호 분야';

CREATE TABLE `news_organizations` (
    `organization_id` BIGINT NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(150) NOT NULL,
    `domain` VARCHAR(255) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `pk_news_organizations` PRIMARY KEY (`organization_id`),
    CONSTRAINT `uk_news_organizations_name` UNIQUE (`name`),
    CONSTRAINT `uk_news_organizations_domain` UNIQUE (`domain`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='정규화된 언론사';

CREATE TABLE `articles` (
    `article_id` BIGINT NOT NULL AUTO_INCREMENT,
    `organization_id` BIGINT NOT NULL,
    `title` VARCHAR(500) NOT NULL,
    `url` TEXT NOT NULL,
    `url_hash` BINARY(32) NOT NULL,
    `published_at` DATETIME(6) NOT NULL,
    `source_category` VARCHAR(100) NULL,
    `topic_code` VARCHAR(32) NULL,
    `subtopic_code` VARCHAR(64) NULL,
    `reporter` VARCHAR(100) NULL,
    `content` MEDIUMTEXT NOT NULL,
    `content_type` VARCHAR(32) NOT NULL,
    `summary` TEXT NULL,
    `summary_status` VARCHAR(32) NOT NULL DEFAULT 'NOT_REQUESTED',
    `analysis_status` VARCHAR(32) NOT NULL DEFAULT 'PROCESSING',
    `node_id` CHAR(36) NULL,
    `content_updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `summary_generated_at` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    INDEX `idx_articles_organization_published`
        (`organization_id`, `published_at` DESC),
    CONSTRAINT `pk_articles` PRIMARY KEY (`article_id`),
    CONSTRAINT `uk_articles_url_hash` UNIQUE (`url_hash`),
    CONSTRAINT `uk_articles_node_id` UNIQUE (`node_id`),
    CONSTRAINT `fk_articles_organization`
        FOREIGN KEY (`organization_id`)
        REFERENCES `news_organizations` (`organization_id`)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='기사 원본 및 서비스용 요약';

CREATE INDEX `idx_articles_published_at`
    ON `articles` (`published_at` DESC);

CREATE INDEX `idx_articles_analysis_published`
    ON `articles` (`analysis_status`, `published_at` DESC);

CREATE INDEX `idx_articles_topic_subtopic_published`
    ON `articles` (`topic_code`, `subtopic_code`, `published_at` DESC);

CREATE TABLE `article_reads` (
    `user_id` BIGINT NOT NULL,
    `article_id` BIGINT NOT NULL,
    `first_read_at` DATETIME(6) NOT NULL,
    `last_read_at` DATETIME(6) NOT NULL,
    `click_count` INT UNSIGNED NOT NULL DEFAULT 1,
    INDEX `idx_article_reads_article_user` (`article_id`, `user_id`),
    CONSTRAINT `pk_article_reads` PRIMARY KEY (`user_id`, `article_id`),
    CONSTRAINT `fk_article_reads_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT `fk_article_reads_article`
        FOREIGN KEY (`article_id`) REFERENCES `articles` (`article_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT `ck_article_reads_click_count`
        CHECK (`click_count` >= 1),
    CONSTRAINT `ck_article_reads_time_order`
        CHECK (`first_read_at` <= `last_read_at`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='뉴스 카드 클릭 기준 기사 열람 기록';

CREATE INDEX `idx_article_reads_user_recent`
    ON `article_reads` (`user_id`, `last_read_at` DESC);

CREATE TABLE `user_knowledge_nodes` (
    `user_id` BIGINT NOT NULL,
    `node_label` VARCHAR(255) NOT NULL,
    `node_type` VARCHAR(32) NOT NULL,
    `node_id` CHAR(36) NOT NULL,
    `topic_code` VARCHAR(32) NULL,
    `read_article_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `node_click_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `first_seen_at` DATETIME(6) NOT NULL,
    `last_seen_at` DATETIME(6) NOT NULL,
    CONSTRAINT `pk_user_knowledge_nodes`
        PRIMARY KEY (`user_id`, `node_type`, `node_id`),
    CONSTRAINT `fk_user_knowledge_nodes_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT `ck_user_knowledge_nodes_time_order`
        CHECK (`first_seen_at` <= `last_seen_at`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자 지식 노드 참조 및 누적 정보';

CREATE INDEX `idx_user_knowledge_nodes_user_recent`
    ON `user_knowledge_nodes` (`user_id`, `last_seen_at` DESC);

CREATE INDEX `idx_user_knowledge_nodes_node_user`
    ON `user_knowledge_nodes` (`node_type`, `node_id`, `user_id`);

CREATE TABLE `trends` (
    `trend_item_id` BIGINT NOT NULL AUTO_INCREMENT,
    `snapshot_at` DATETIME(6) NOT NULL,
    `node_type` VARCHAR(32) NOT NULL,
    `node_id` CHAR(36) NOT NULL,
    `rank` INT UNSIGNED NOT NULL,
    `article_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `growth_rate` DECIMAL(10,4) NULL,
    `trend_score` DECIMAL(10,4) NOT NULL,
    CONSTRAINT `pk_trends` PRIMARY KEY (`trend_item_id`),
    CONSTRAINT `uk_trends_snapshot_node`
        UNIQUE (`snapshot_at`, `node_type`, `node_id`),
    CONSTRAINT `uk_trends_snapshot_rank`
        UNIQUE (`snapshot_at`, `rank`),
    CONSTRAINT `ck_trends_rank`
        CHECK (`rank` >= 1)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='시점별 통합 노드 트렌드 순위';

CREATE INDEX `idx_trends_node_snapshot`
    ON `trends` (`node_type`, `node_id`, `snapshot_at` DESC);

CREATE TABLE `user_article_favorites` (
    `user_id` BIGINT NOT NULL,
    `article_id` BIGINT NOT NULL,
    `favorited_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT `pk_user_article_favorites`
        PRIMARY KEY (`user_id`, `article_id`),
    CONSTRAINT `fk_user_article_favorites_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT `fk_user_article_favorites_article`
        FOREIGN KEY (`article_id`) REFERENCES `articles` (`article_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자 기사 즐겨찾기';

CREATE TABLE `user_node_favorites` (
    `user_id` BIGINT NOT NULL,
    `node_type` VARCHAR(32) NOT NULL,
    `node_id` CHAR(36) NOT NULL,
    `favorited_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT `pk_user_node_favorites`
        PRIMARY KEY (`user_id`, `node_type`, `node_id`),
    CONSTRAINT `fk_user_node_favorites_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자 Neo4j 노드 즐겨찾기';

CREATE TABLE `recommendation_events` (
    `event_id` CHAR(36) NOT NULL,
    `title` VARCHAR(500) NOT NULL,
    `summary` TEXT NULL,
    `summary_status` VARCHAR(32) NOT NULL DEFAULT 'NOT_REQUESTED',
    `topic_code` VARCHAR(32) NOT NULL,
    `event_updated_at` DATETIME(6) NULL,
    `summary_generated_at` DATETIME(6) NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `pk_recommendation_events` PRIMARY KEY (`event_id`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='추천 Event 공통 표시 정보 및 요약 캐시';

CREATE INDEX `idx_recommendation_events_summary_status`
    ON `recommendation_events` (`summary_status`);

CREATE INDEX `idx_recommendation_events_topic_code`
    ON `recommendation_events` (`topic_code`);

CREATE TABLE `user_recommendations` (
    `user_recommendation_id` BIGINT NOT NULL AUTO_INCREMENT,
    `user_id` BIGINT NOT NULL,
    `event_id` CHAR(36) NOT NULL,
    `recommendation_type` VARCHAR(32) NOT NULL,
    `recommendation_score` DECIMAL(10,6) NOT NULL,
    `rank` TINYINT UNSIGNED NOT NULL,
    `reason` VARCHAR(100) NULL,
    `recommended_at` DATETIME(6) NOT NULL,
    `cycle` VARCHAR(8) NOT NULL,
    `available_at` DATETIME(6) NOT NULL,
    INDEX `idx_user_recommendations_event` (`event_id`),
    CONSTRAINT `pk_user_recommendations`
        PRIMARY KEY (`user_recommendation_id`),
    CONSTRAINT `uk_user_recommendations_event`
        UNIQUE (`user_id`, `available_at`, `recommendation_type`, `event_id`),
    CONSTRAINT `uk_user_recommendations_rank`
        UNIQUE (`user_id`, `available_at`, `recommendation_type`, `rank`),
    CONSTRAINT `fk_user_recommendations_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT `fk_user_recommendations_event`
        FOREIGN KEY (`event_id`) REFERENCES `recommendation_events` (`event_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE,
    CONSTRAINT `ck_user_recommendations_rank`
        CHECK (`rank` >= 1)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='사용자별 회차 추천 결과';

-- TopicCode 허용값:
-- POLITICS, ECONOMY, SOCIETY, CULTURE, INTERNATIONAL, SPORTS, IT_SCIENCE
-- TopicCode, SubtopicCode 및 상태·유형 코드는 DB ENUM이 아닌 문자열로 저장한다.
-- 허용값과 한글→영문 매핑은 Spring Boot와 FastAPI의 공통 계약으로 검증한다.

-- Neo4j 논리 참조(FK 생성 안 함):
-- articles.node_id               -> Article.nodeId
-- user_knowledge_nodes.node_id   -> 해당 Label의 nodeId
-- user_node_favorites.node_id    -> 해당 Label의 nodeId
-- trends.node_id                 -> 해당 Label의 nodeId
-- recommendation_events.event_id -> Event.nodeId
