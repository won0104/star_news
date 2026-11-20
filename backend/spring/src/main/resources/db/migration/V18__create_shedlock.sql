-- 배치 분산 잠금(ShedLock).
-- @Scheduled 는 인스턴스마다 따로 돈다. 앱을 두 대 띄우면 수집·분석·추천이 두 번씩 돌아 AI 워커와
-- GNews 한도를 두 배로 쓰고 추천 회차가 겹친다. 배치 이름당 행 하나를 두고, 먼저 잡은 인스턴스만 돈다.
--
-- 시각은 UTC 다. 다른 테이블은 KST 로 찍지만, ShedLock 은 인스턴스 시계 차이를 피하려고 DB 서버
-- 시계(UTC_TIMESTAMP(3))로 잠금을 잰다(usingDbTime). TIMESTAMP 대신 DATETIME 을 쓰는 이유도 같다.
-- TIMESTAMP 는 세션 시간대로 바꿔 저장·조회하므로, 세션 시간대가 다른 연결이 섞이면 같은 값을 다르게
-- 읽는다. DATETIME 은 넣은 UTC 값을 그대로 둔다. 사람이 볼 때는 KST 로 9시간 더해 읽는다.
CREATE TABLE `shedlock` (
    `name` VARCHAR(64) NOT NULL,
    `lock_until` DATETIME(3) NOT NULL,
    `locked_at` DATETIME(3) NOT NULL,
    `locked_by` VARCHAR(255) NOT NULL,
    CONSTRAINT `pk_shedlock` PRIMARY KEY (`name`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='배치 분산 잠금 (시각은 UTC)';
