-- 기사 분석 회차의 실행 기록.
-- 지금은 회차 결과가 로그에만 남아, 컨테이너를 다시 띄우면 사라진다. 며칠치 처리량과 밀린 정도를
-- 나중에 볼 수 없어 시간 예산 같은 설정을 바꿔도 효과를 잴 수 없다.
-- 추천 배치(recommendation_runs)와 같은 방식으로 남긴다.
CREATE TABLE `article_analysis_runs` (
    `run_id` BIGINT NOT NULL AUTO_INCREMENT,
    `status` VARCHAR(32) NOT NULL,
    `waiting_before` INT NOT NULL DEFAULT 0,
    `processed` INT NOT NULL DEFAULT 0,
    `completed` INT NOT NULL DEFAULT 0,
    `dropped` INT NOT NULL DEFAULT 0,
    `will_retry` INT NOT NULL DEFAULT 0,
    `gave_up` INT NOT NULL DEFAULT 0,
    `errors` INT NOT NULL DEFAULT 0,
    `remaining` INT NOT NULL DEFAULT 0,
    `oldest_wait_minutes` BIGINT NULL,
    `started_at` DATETIME(6) NOT NULL,
    `finished_at` DATETIME(6) NULL,
    CONSTRAINT `pk_article_analysis_runs` PRIMARY KEY (`run_id`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='기사 분석 회차 실행 상태';

-- 최근 회차부터 보거나 기간으로 끊어 보는 조회에 쓴다.
CREATE INDEX `idx_article_analysis_runs_started_at`
    ON `article_analysis_runs` (`started_at`);
