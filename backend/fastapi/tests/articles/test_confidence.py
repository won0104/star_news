from datetime import datetime, timezone

from app.articles import repository
from app.database import _driver

START_ID = "test-confidence-event"
END_ID = "test-confidence-entity"


def _setup():
    with _driver.session() as session:
        session.run("MATCH (n) WHERE n.nodeId IN [$a, $b] DETACH DELETE n", a=START_ID, b=END_ID)
        session.run("CREATE (:Event {nodeId: $a}), (:Entity {nodeId: $b})", a=START_ID, b=END_ID)


def _teardown():
    with _driver.session() as session:
        session.run("MATCH (n) WHERE n.nodeId IN [$a, $b] DETACH DELETE n", a=START_ID, b=END_ID)


def _merge(confidence):
    with _driver.session() as session:
        repository.merge_simple_edge(session, "ACTOR", START_ID, END_ID, confidence, datetime.now(timezone.utc))


def _confidence():
    with _driver.session() as session:
        return session.run(
            "MATCH (:Event {nodeId: $a})-[r:ACTOR]->(:Entity {nodeId: $b}) RETURN r.confidence AS c",
            a=START_ID, b=END_ID,
        ).single()["c"]


# 같은 관계가 다른 기사에서 다시 나와도 확신이 가장 높았던 값을 남긴다.
def test_repeated_edge_keeps_highest_confidence():
    _setup()
    try:
        _merge(0.9)
        _merge(0.6)
        assert _confidence() == 0.9

        _merge(0.95)
        assert _confidence() == 0.95
    finally:
        _teardown()


def test_missing_confidence_does_not_erase_existing_value():
    _setup()
    try:
        _merge(0.8)
        _merge(None)
        assert _confidence() == 0.8
    finally:
        _teardown()


def test_first_confidence_is_stored_even_if_low():
    _setup()
    try:
        _merge(0.1)
        assert _confidence() == 0.1
    finally:
        _teardown()
