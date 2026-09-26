from datetime import datetime, timezone

from app.articles import repository
from app.database import _driver

EMBEDDING_DIMENSIONS = 1024


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


# 실측 확인: Neo4j 벡터 인덱스는 같은 트랜잭션의 미커밋 쓰기를 못 봄 - 그래서 한 기사에서 AI가
# 사실상 같은 사건을 Event 2개로 나눠 줘도(커밋 전) 벡터 검색만으론 서로를 못 찾고 중복 생성됨.
# in_batch_candidates로 직전에 처리한 Event 정보를 넘기면, 커밋 여부와 무관하게 파이썬에서
# 직접 비교해서 병합되는지 확인한다.
def test_merge_event_node_dedupes_against_in_batch_candidate_without_commit():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            # 다른 테스트 파일들이 자주 쓰는 index 0~10대는 로컬 DB에 남은 잔여 데이터와 겹칠 수 있어 피함
            embedding = _unit_vector(900)
            first_id, first_is_new = repository.merge_event_node(
                tx, "3연속 실점해", embedding, "test-model", now, now,
                ["대표팀", "태국"], ["태국", "대표팀"],
            )
            assert first_is_new is True

            in_batch_candidates = [{
                "nodeId": first_id, "embedding": embedding,
                "actorNames": ["대표팀", "태국"], "targetNames": ["태국", "대표팀"],
            }]

            second_id, second_is_new = repository.merge_event_node(
                tx, "3연속 실점해", embedding, "test-model", now, now,
                ["대표팀", "태국"], ["태국", "대표팀"], in_batch_candidates,
            )

            assert second_id == first_id
            assert second_is_new is False
        finally:
            tx.rollback()


# Actor/Target이 확실히 다르면(다른 사건) in_batch 후보가 아무리 유사도가 높아도 재사용하지 않고
# 새로 생성해야 함 - "금메달을 목에 걸었다"처럼 짧고 일반적인 문장이 서로 다른 선수/종목을
# 가리키는 경우를 잘못 합치면 안 되기 때문
def test_merge_event_node_creates_new_when_in_batch_candidate_conflicts():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            embedding = _unit_vector(901)
            first_id, _ = repository.merge_event_node(
                tx, "금메달을 목에 걸었다", embedding, "test-model", now, now,
                ["장잔숴", "일본"], ["자유형 1,500m"],
            )

            in_batch_candidates = [{
                "nodeId": first_id, "embedding": embedding,
                "actorNames": ["장잔숴", "일본"], "targetNames": ["자유형 1,500m"],
            }]

            second_id, second_is_new = repository.merge_event_node(
                tx, "금메달을 목에 걸었다", embedding, "test-model", now, now,
                ["위이팅", "중국"], ["여자 평영 100m"], in_batch_candidates,
            )

            assert second_id != first_id
            assert second_is_new is True
        finally:
            tx.rollback()


# in_batch_candidates를 안 넘겨도(None, 기본값) 기존처럼 동작해야 함 - 하위 호환 확인
def test_merge_event_node_works_without_in_batch_candidates():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            node_id, is_new = repository.merge_event_node(
                tx, "제목", _unit_vector(902), "test-model", now, now, [], [],
            )
            assert is_new is True
            assert node_id
        finally:
            tx.rollback()
