-- 추천 생성 회차의 실행 기록.
-- 로그만으로는 회차가 끝났는지, 몇 명이 추천을 못 받았는지 나중에 확인할 수 없다.
-- 같은 공개 시각으로 여러 번 돌 수 있다(수동 재실행). 그래서 available_at 에 유일 제약을 두지 않는다.
CREATE TABLE `recommendation_runs` (
    `run_id` BIGINT NOT NULL AUTO_INCREMENT,
    `cycle` VARCHAR(8) NOT NULL,
    `available_at` DATETIME(6) NOT NULL,
    `status` VARCHAR(16) NOT NULL,
    `total_chunks` INT NOT NULL DEFAULT 0,
    `failed_chunks` INT NOT NULL DEFAULT 0,
    `target_users` INT NOT NULL DEFAULT 0,
    `stored_users` INT NOT NULL DEFAULT 0,
    `failed_users` INT NOT NULL DEFAULT 0,
    `started_at` DATETIME(6) NOT NULL,
    `finished_at` DATETIME(6) NULL,
    CONSTRAINT `pk_recommendation_runs` PRIMARY KEY (`run_id`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='추천 생성 회차 실행 상태';

CREATE INDEX `idx_recommendation_runs_available_at`
    ON `recommendation_runs` (`available_at`, `status`);

-- 회차 안의 묶음 하나. 묶음에 담았던 사용자 목록을 남겨 두어, 실패한 묶음을 같은 사용자로 다시 보낼 수 있다.
-- 사용자 조회는 페이지 순서라 다시 읽으면 그 사이 가입·탈퇴로 경계가 밀린다.
CREATE TABLE `recommendation_run_chunks` (
    `chunk_id` BIGINT NOT NULL AUTO_INCREMENT,
    `run_id` BIGINT NOT NULL,
    `chunk_no` INT NOT NULL,
    `user_ids` JSON NOT NULL,
    `user_count` INT NOT NULL,
    `status` VARCHAR(16) NOT NULL,
    `attempts` INT NOT NULL DEFAULT 1,
    `failure_code` VARCHAR(64) NULL,
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    CONSTRAINT `pk_recommendation_run_chunks` PRIMARY KEY (`chunk_id`),
    CONSTRAINT `uk_recommendation_run_chunks_no` UNIQUE (`run_id`, `chunk_no`),
    CONSTRAINT `fk_recommendation_run_chunks_run`
        FOREIGN KEY (`run_id`) REFERENCES `recommendation_runs` (`run_id`)
        ON UPDATE RESTRICT
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='추천 생성 회차의 사용자 묶음별 결과';
