-- 트렌드 조회가 Neo4j에 의존하지 않도록 집계 시점의 Node 표시 이름을 함께 저장한다.
ALTER TABLE `trends`
    ADD COLUMN `node_title` VARCHAR(500) NOT NULL DEFAULT ''
    AFTER `node_id`;

-- 기존 행 보정에만 사용한 기본값은 제거하여 이후 집계에서 제목 입력을 강제한다.
ALTER TABLE `trends`
    ALTER COLUMN `node_title` DROP DEFAULT;

-- 급상승률을 제공하지 않기로 한 현재 트렌드 정책을 스키마에 반영한다.
ALTER TABLE `trends`
    DROP COLUMN `growth_rate`;
