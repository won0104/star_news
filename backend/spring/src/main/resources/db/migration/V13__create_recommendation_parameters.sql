-- 추천 가중치 재튜닝 결과.
-- 주 1회 FastAPI 가 그리드서치로 계산한 값을 받아 남긴다. 추천 회차는 가장 최근 행을 읽어 쓴다.
-- 행을 갈아끼우지 않고 쌓는다. 주차별로 가중치와 지표를 견줘야 어느 설정이 나았는지 알 수 있다.
CREATE TABLE `recommendation_parameters` (
    `parameter_id` BIGINT NOT NULL AUTO_INCREMENT,
    `cbf_weight` DECIMAL(5,4) NOT NULL,
    `cf_weight` DECIMAL(5,4) NOT NULL,
    `ndcg_at10` DECIMAL(6,4) NULL,
    `hit_rate_at10` DECIMAL(6,4) NULL,
    `recall_at10` DECIMAL(6,4) NULL,
    `computed_at` DATETIME(6) NOT NULL,
    CONSTRAINT `pk_recommendation_parameters` PRIMARY KEY (`parameter_id`),
    CONSTRAINT `ck_recommendation_parameters_weights`
        CHECK (`cbf_weight` BETWEEN 0 AND 1 AND `cf_weight` BETWEEN 0 AND 1)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci
  COMMENT='추천 가중치 재튜닝 이력';
