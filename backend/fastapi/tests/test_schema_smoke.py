"""CI Neo4j 스키마(V1/V2) 적용 여부를 가볍게 확인한다."""

from app.database import _driver


def test_neo4j_core_constraints_exist() -> None:
    with _driver.session() as session:
        names = {
            row["name"]
            for row in session.run("SHOW CONSTRAINTS YIELD name RETURN name").data()
        }
    expected = {
        "article_node_id_unique",
        "event_node_id_unique",
        "topic_code_unique",
        "entity_node_id_unique",
        "user_id_unique",
    }
    missing = expected - names
    assert not missing, f"missing constraints: {sorted(missing)}"


def test_event_vector_index_online() -> None:
    with _driver.session() as session:
        rows = session.run(
            """
            SHOW INDEXES
            YIELD name, type, state
            WHERE name = 'event_embedding_index'
            RETURN name, type, state
            """
        ).data()
    assert rows, "event_embedding_index not found"
    assert rows[0]["state"] == "ONLINE"
