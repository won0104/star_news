-- MySQL 기사 분석 상태와 Neo4j Article 노드를 맞대 보는 대사(대조) 배치의 기록.
--
-- 두 저장소는 분산 트랜잭션으로 묶지 않는다. 분석 응답이 유실되면 재요청 때 Neo4j 의 완료 결과를
-- 재사용해 복구하지만, 그 복구는 "다시 요청이 올 때"만 일어난다. 요청이 다시 오지 않는 어긋남
-- (COMPLETED 인데 그래프에 기사가 없음, 그래프에는 있는데 FAILED 로 굳음 등)은 아무도 모른 채 남는다.
-- 하루 한 번 양쪽을 전수 비교해 어긋남을 세고, 무엇이 어긋났는지 남긴다.
CREATE TABLE `graph_reconciliation_runs` (
    `run_id` BIGINT NOT NULL AUTO_INCREMENT,
    `status` VARCHAR(32) NOT NULL,
    `mysql_checked` INT NOT NULL DEFAULT 0,
    `graph_checked` INT NOT NULL DEFAULT 0,
    `missing_graph` INT NOT NULL DEFAULT 0,
    `node_id_mismatch` INT NOT NULL DEFAULT 0,
    `unreflected` INT NOT NULL DEFAULT 0,
    `orphan_graph` INT NOT NULL DEFAULT 0,
    `dropped_with_graph` INT NOT NULL DEFAULT 0,
    `requeued` INT NOT NULL DEFAULT 0,
    `started_at` DATETIME(6) NOT NULL,
    `finished_at` DATETIME(6) NULL,
    CONSTRAINT `pk_graph_reconciliation_runs` PRIMARY KEY (`run_id`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='MySQL·Neo4j 대사 회차 실행 기록';

CREATE INDEX `idx_graph_reconciliation_runs_started_at`
    ON `graph_reconciliation_runs` (`started_at`);

-- 회차에서 찾은 어긋남 한 건. 건수는 회차 기록에 모두 세고, 상세는 회차당 상한까지만 남긴다.
-- 기사 행을 지워도 기록은 남아야 하므로 articles 에 외래 키를 걸지 않는다.
CREATE TABLE `graph_reconciliation_issues` (
    `issue_id` BIGINT NOT NULL AUTO_INCREMENT,
    `run_id` BIGINT NOT NULL,
    `issue_type` VARCHAR(32) NOT NULL,
    `article_id` BIGINT NOT NULL,
    `mysql_status` VARCHAR(32) NULL,
    `mysql_node_id` CHAR(36) NULL,
    `graph_node_id` VARCHAR(64) NULL,
    `action` VARCHAR(32) NOT NULL,
    `created_at` DATETIME(6) NOT NULL,
    CONSTRAINT `pk_graph_reconciliation_issues` PRIMARY KEY (`issue_id`),
    CONSTRAINT `fk_graph_reconciliation_issues_run`
        FOREIGN KEY (`run_id`) REFERENCES `graph_reconciliation_runs` (`run_id`) ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='MySQL·Neo4j 대사에서 찾은 어긋남';

CREATE INDEX `idx_graph_reconciliation_issues_run`
    ON `graph_reconciliation_issues` (`run_id`, `issue_type`);
