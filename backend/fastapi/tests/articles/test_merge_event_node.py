from datetime import datetime, timezone

from app.articles import repository
from app.database import _driver

EMBEDDING_DIMENSIONS = 1024
TOPIC_CODE = "SPORTS"  # 로컬 DB에 항상 시드되어 있는 실제 Topic - assign_event_to_story 테스트에 씀


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


# assign_event_to_story도 merge_event_node와 같은 이유(벡터 인덱스가 같은 트랜잭션의 미커밋
# 쓰기를 못 봄)로, 한 기사 안에서 관련된 새 Event가 여러 개 나오면 서로를 못 찾고 따로 외톨이로
# 남거나 따로 Story를 만들 수 있음. in_batch_stories/in_batch_orphans로 이 사각지대를 메우는지 확인
def test_assign_event_to_story_pairs_two_orphans_in_same_article_without_commit():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            embedding = _unit_vector(910)
            stories_in_this_article: list[dict] = []
            orphans_in_this_article: list[dict] = []

            # 첫 Event - 후보가 하나도 없으니(커밋된 것도, 같은 기사 안 이전 것도 없음) 외톨이로 남음
            first_result = repository.assign_event_to_story(
                tx, "event-1", "1차 발표", embedding, "test-model", TOPIC_CODE, now, now,
                ["대표팀", "태국"], ["태국", "대표팀"], stories_in_this_article, orphans_in_this_article,
            )
            assert first_result is None
            assert orphans_in_this_article[0]["nodeId"] == "event-1"

            # 두 번째 Event - 첫 Event와 유사도 높고 Actor/Target도 겹침 -> 같은 기사 안의 외톨이(event-1)를
            # 찾아서 둘을 묶어 새 Story로 승격해야 함 (커밋 전이라 벡터 검색으로는 절대 못 찾는 상황)
            second_result = repository.assign_event_to_story(
                tx, "event-2", "후속 조치", embedding, "test-model", TOPIC_CODE, now, now,
                ["대표팀", "태국"], ["태국", "대표팀"], stories_in_this_article, orphans_in_this_article,
            )

            assert second_result is not None
            # 승격된 event-1은 더 이상 외톨이가 아니므로 목록에서 빠지고, 새 Story가 등록돼야 함
            assert orphans_in_this_article == []
            assert stories_in_this_article[0]["nodeId"] == second_result
        finally:
            tx.rollback()


# 새로 만들어진 Story도(커밋 전) 같은 기사의 다음 Event가 in_batch_stories로 찾아서 편입할 수 있어야 함
def test_assign_event_to_story_joins_newly_created_story_in_same_article():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            embedding = _unit_vector(911)
            stories_in_this_article: list[dict] = []
            orphans_in_this_article: list[dict] = []

            repository.assign_event_to_story(
                tx, "event-a", "1차 발표", embedding, "test-model", TOPIC_CODE, now, now,
                ["대표팀", "태국"], ["태국", "대표팀"], stories_in_this_article, orphans_in_this_article,
            )
            story_id = repository.assign_event_to_story(
                tx, "event-b", "후속 조치", embedding, "test-model", TOPIC_CODE, now, now,
                ["대표팀", "태국"], ["태국", "대표팀"], stories_in_this_article, orphans_in_this_article,
            )

            # 세 번째 Event - 방금 만들어진(아직 미커밋) Story에 편입돼야 함
            third_result = repository.assign_event_to_story(
                tx, "event-c", "세 번째 소식", embedding, "test-model", TOPIC_CODE, now, now,
                ["대표팀", "태국"], ["태국", "대표팀"], stories_in_this_article, orphans_in_this_article,
            )
            assert third_result == story_id
        finally:
            tx.rollback()


# Actor/Target이 확실히 다르면(다른 사건) 유사도가 아무리 높아도 같은 기사 안의 외톨이끼리도 안 묶여야 함
def test_assign_event_to_story_does_not_pair_conflicting_orphans_in_same_article():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            embedding = _unit_vector(912)
            stories_in_this_article: list[dict] = []
            orphans_in_this_article: list[dict] = []

            repository.assign_event_to_story(
                tx, "event-x", "금메달을 목에 걸었다", embedding, "test-model", TOPIC_CODE, now, now,
                ["장잔숴", "일본"], ["자유형 1,500m"], stories_in_this_article, orphans_in_this_article,
            )
            second_result = repository.assign_event_to_story(
                tx, "event-y", "금메달을 목에 걸었다", embedding, "test-model", TOPIC_CODE, now, now,
                ["위이팅", "중국"], ["여자 평영 100m"], stories_in_this_article, orphans_in_this_article,
            )

            assert second_result is None  # 새 Story로 안 묶이고 자기도 외톨이로 남아야 함
            assert stories_in_this_article == []
            assert len(orphans_in_this_article) == 2
        finally:
            tx.rollback()


# in_batch_stories/in_batch_orphans를 안 넘겨도(None, 기본값) 기존처럼 동작해야 함 - 하위 호환 확인
def test_assign_event_to_story_works_without_in_batch_lists():
    now = datetime.now(timezone.utc)
    with _driver.session() as session:
        tx = session.begin_transaction()
        try:
            result = repository.assign_event_to_story(
                tx, "event-solo", "제목", _unit_vector(913), "test-model", TOPIC_CODE, now, now, [], [],
            )
            assert result is None  # 후보가 없으니 외톨이로 남음, 에러 없이 동작
        finally:
            tx.rollback()
