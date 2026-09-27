from datetime import datetime, timezone

from app.articles import repository
from app.database import _driver

# 공유 로컬 DB에 다른 테스트(test_analyze.py 등)가 남긴 실제 Entity와 절대 안 겹치도록
# 평범한 단어 대신 이 테스트 파일 전용 토큰을 씀
NAME_A = "test-merge-entity-token-alpha"
NAME_B = "test-merge-entity-token-beta"
NAME_C = "test-merge-entity-token-gamma"


def _reset_fixture(session):
    session.run(
        "MATCH (e:Entity) WHERE e.canonicalName IN [$a, $b, $c] DETACH DELETE e",
        a=NAME_A, b=NAME_B, c=NAME_C,
    )


# 새로 만들 때는 aliases가 빈 채로 시작해야 함 (merged_mentions 텍스트는 저장 안 함)
def test_merge_extracted_entity_creates_with_empty_aliases():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        _reset_fixture(session)
        node_id = repository.merge_extracted_entity(session, NAME_A, "PERSON", now, [NAME_B])
        aliases = session.run(
            "MATCH (e:Entity {nodeId: $id}) RETURN e.aliases AS aliases", id=node_id
        ).single()["aliases"]
        _reset_fixture(session)

    assert aliases == []


# 자기 canonicalName으로 그대로 매칭되면(같은 이름 재사용) aliases에 아무것도 안 추가됨
def test_merge_extracted_entity_reuses_same_name_without_adding_alias():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        _reset_fixture(session)
        first_id = repository.merge_extracted_entity(session, NAME_A, "PERSON", now)
        second_id = repository.merge_extracted_entity(session, NAME_A, "PERSON", now, [NAME_B])
        aliases = session.run(
            "MATCH (e:Entity {nodeId: $id}) RETURN e.aliases AS aliases", id=second_id
        ).single()["aliases"]
        _reset_fixture(session)

    assert first_id == second_id
    assert aliases == []


# alias 중 하나가 기존 "다른" Entity의 canonicalName과 겹치면, 새로 안 만들고 그 노드를 재사용하며
# 지금 canonicalName을 그 노드의 aliases에 남겨야 함
def test_merge_extracted_entity_merges_into_existing_node_matched_by_alias():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        _reset_fixture(session)
        # 먼저 NAME_B를 자기 canonicalName으로 하는 Entity를 만들어 둠
        existing_id = repository.merge_extracted_entity(session, NAME_B, "PERSON", now)
        # 이번엔 NAME_A로 오는데, alias 목록에 NAME_B가 있음 -> NAME_B 노드로 편입돼야 함
        merged_id = repository.merge_extracted_entity(session, NAME_A, "PERSON", now, [NAME_B])
        aliases = session.run(
            "MATCH (e:Entity {nodeId: $id}) RETURN e.aliases AS aliases", id=merged_id
        ).single()["aliases"]
        _reset_fixture(session)

    assert merged_id == existing_id  # 새로 안 만들고 기존 노드 재사용
    assert aliases == [NAME_A]  # merged_mentions(NAME_B) 자체는 안 남고, 편입된 canonicalName만 남음


# 같은 alias로 여러 번 겹쳐도 aliases에 중복으로 쌓이지 않아야 함
def test_merge_extracted_entity_does_not_duplicate_alias_on_repeated_merge():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        _reset_fixture(session)
        repository.merge_extracted_entity(session, NAME_B, "PERSON", now)
        repository.merge_extracted_entity(session, NAME_A, "PERSON", now, [NAME_B])
        node_id = repository.merge_extracted_entity(session, NAME_A, "PERSON", now, [NAME_B])
        aliases = session.run(
            "MATCH (e:Entity {nodeId: $id}) RETURN e.aliases AS aliases", id=node_id
        ).single()["aliases"]
        _reset_fixture(session)

    assert aliases == [NAME_A]


# entityType이 다르면(PERSON vs ORGANIZATION) alias가 겹쳐도 병합하지 않고 새로 만들어야 함
def test_merge_extracted_entity_does_not_merge_across_different_entity_types():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        _reset_fixture(session)
        org_id = repository.merge_extracted_entity(session, NAME_B, "ORGANIZATION", now)
        person_id = repository.merge_extracted_entity(session, NAME_A, "PERSON", now, [NAME_B])
        _reset_fixture(session)

    assert person_id != org_id


# aliases를 안 넘겨도(None, 기본값) 기존처럼 동작해야 함 - 하위 호환 확인
def test_merge_extracted_entity_works_without_aliases():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        _reset_fixture(session)
        node_id = repository.merge_extracted_entity(session, NAME_A, "PERSON", now)
        aliases = session.run(
            "MATCH (e:Entity {nodeId: $id}) RETURN e.aliases AS aliases", id=node_id
        ).single()["aliases"]
        _reset_fixture(session)

    assert aliases == []
