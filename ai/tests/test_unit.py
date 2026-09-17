"""Unit tests that do not require model weights."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

import json
from pathlib import Path

from starlight_ai.adapter.neo4j_schema import adapt_to_schema
from starlight_ai.batch.postprocess import postprocess_bundle
from starlight_ai.device import resolve_device
from starlight_ai.entity_filter import is_noise_entity_name
from starlight_ai.preprocess import preprocess_content
from starlight_ai.topic_map import topic_name_ko


def test_preprocess_keeps_sentence_lines():
    raw = "짧은\n서울시는 지원을 확대한다고 발표했다.\n@spam"
    out = preprocess_content(raw)
    assert "서울시는" in out
    assert "@spam" not in out


def test_noise_entity_filter():
    assert is_noise_entity_name('"')
    assert is_noise_entity_name('""')
    assert is_noise_entity_name("그")
    assert is_noise_entity_name("그녀")
    assert is_noise_entity_name("형")
    assert is_noise_entity_name("동생")
    assert is_noise_entity_name(" 그 ")
    assert not is_noise_entity_name("윤석열")
    assert not is_noise_entity_name("더불어민주당")
    assert not is_noise_entity_name("LG유플러스")


def test_topic_name_ko_it_science():
    assert topic_name_ko("IT_과학") == "IT·과학"
    assert topic_name_ko("경제") == "경제"


def test_resolve_device_cpu_forced(monkeypatch):
    monkeypatch.setenv("STARLIGHT_AI_DEVICE", "cpu")
    assert resolve_device(None) == "cpu"
    assert resolve_device("cpu") == "cpu"


def test_adapt_maps_v2_kinds_and_embedding():
    article = {
        "article_id": "a1",
        "title": "테스트",
        "published_at": "2026-09-08T09:00:00+09:00",
        "mysql_article_id": 1,
        "content": "x",
    }
    kg = {
        "schema_version": "articlelocal-kg-public-v2",
        "status": "PUBLIC_ARTICLE_LOCAL_KG_READY",
        "validation": {"status": "PASS"},
        "nodes": [
            {
                "node_id": "ART-1",
                "kind": "ARTICLE",
                "properties": {"title": "테스트", "published_at": "2026-09-08T09:00:00+09:00"},
            },
            {
                "node_id": "EVT-1",
                "kind": "EVENT",
                "properties": {"text": "정부가 정책을 발표했다"},
            },
            {
                "node_id": "LEVT-1",
                "kind": "LOCAL_EVENT",
                "properties": {"text": "정부가 정책을 발표했다"},
            },
            {
                "node_id": "ENT-1",
                "kind": "ENTITY",
                "properties": {"canonical_name": "정부", "entity_type": "ORGANIZATION"},
            },
            {
                "node_id": "ENT-2",
                "kind": "ENTITY",
                "properties": {"canonical_name": "김씨", "entity_type": "PERSON"},
            },
            {
                "node_id": "ENT-NOISE-1",
                "kind": "ENTITY",
                "properties": {"canonical_name": '"', "entity_type": "PERSON"},
            },
            {
                "node_id": "ENT-NOISE-2",
                "kind": "ENTITY",
                "properties": {"canonical_name": "그", "entity_type": "PERSON"},
            },
            {
                "node_id": "TIME-1",
                "kind": "TIME",
                "properties": {"normalized_value": "2026-09-08", "granularity": "DAY"},
            },
            {
                "node_id": "STP-1",
                "kind": "STATEMENT",
                "properties": {"text": "효과가 클 것이다", "statement_type": "FORECAST"},
            },
        ],
        "edges": [
            {
                "edge_id": "e1",
                "edge_type": "COVERS",
                "source_id": "ART-1",
                "target_id": "EVT-1",
                "confidence": 0.9,
            },
            {
                "edge_id": "e2",
                "edge_type": "CONTAINS_STATEMENT",
                "source_id": "ART-1",
                "target_id": "STP-1",
                "confidence": 0.8,
            },
            {
                "edge_id": "e3",
                "edge_type": "ACTOR",
                "source_id": "EVT-1",
                "target_id": "ENT-1",
                "confidence": 0.7,
            },
            {
                "edge_id": "e4",
                "edge_type": "MEMBER_OF_EVENT",
                "source_id": "EVT-1",
                "target_id": "ENT-1",
            },
            {
                "edge_id": "e5",
                "edge_type": "OCCURRED_ON",
                "source_id": "EVT-1",
                "target_id": "TIME-1",
            },
        ],
    }
    emb = {"EVT-1": [0.1, 0.2, 0.3]}
    out = adapt_to_schema(
        article=article,
        kg=kg,
        classification={"big_cls": "경제", "small_cls": "x", "region_cls": "y", "topic": "경제"},
        event_embeddings=emb,
        embedding_model="nlpai-lab/KURE-v1",
        embedding_dim=3,
    )
    assert out["schema_version"] == "starlight-article-analyze-v1"
    assert out["classification"]["topic"] == "경제"
    assert not any(n["properties"]["nodeId"] == "LEVT-1" for n in out["nodes"])
    event = next(n for n in out["nodes"] if "Event" in n["labels"])
    assert event["properties"]["title"] == "정부가 정책을 발표했다"
    assert event["properties"]["embedding"] == [0.1, 0.2, 0.3]
    org = next(n for n in out["nodes"] if n["properties"].get("canonicalName") == "정부")
    assert org["labels"] == ["Entity"]
    assert org["properties"]["entityType"] == "ORGANIZATION"
    person = next(n for n in out["nodes"] if n["properties"].get("canonicalName") == "김씨")
    assert "Person" in person["labels"]
    assert not any(n["properties"].get("canonicalName") in {'"', "그"} for n in out["nodes"])
    assert any("dropped_noise_entity" in w for w in out["warnings"])
    time_n = next(n for n in out["nodes"] if "Time" in n["labels"])
    assert time_n["properties"]["timeKey"] == "2026-09-08"
    statement = next(n for n in out["nodes"] if "Statement" in n["labels"])
    assert statement["properties"]["text"] == "효과가 클 것이다"
    assert statement["properties"]["statementType"] == "FORECAST"
    edge_types = {e["type"] for e in out["edges"]}
    assert "CONTAINS_STATEMENT" in edge_types
    assert "MEMBER_OF_EVENT" not in edge_types
    assert "PUBLISHED_BY" not in edge_types


def test_adapt_maps_v23_compact_statement_fields():
    """2.3 compact PUBLIC은 Statement에 canonical_text / statement_type_value를 쓴다."""
    article = {
        "article_id": "a23",
        "title": "테스트",
        "published_at": "2026-09-08T09:00:00+09:00",
        "mysql_article_id": 23,
        "content": "x",
    }
    kg = {
        "schema_version": "articlelocal-kg-public-v2.2",
        "status": "PARTIAL",
        "validation": {"status": "PASS"},
        "nodes": [
            {
                "node_id": "ARTICLE-1",
                "kind": "ARTICLE",
                "properties": {"title": "테스트", "published_at": "2026-09-08T09:00:00+09:00"},
            },
            {
                "node_id": "EVENT-1",
                "kind": "EVENT",
                "properties": {"canonical_text": "서울시가 주거 지원을 확대했다"},
            },
            {
                "node_id": "STATEMENT-1",
                "kind": "STATEMENT",
                "properties": {
                    "canonical_text": "다음 달부터 신청을 받는다고 말했다",
                    "statement_type_value": "FORECAST",
                    "statement_type_status": "EXECUTED",
                },
            },
            {
                "node_id": "ENTITY-1",
                "kind": "ENTITY",
                "properties": {"canonical_name": "서울시", "entity_type": "ORGANIZATION"},
            },
        ],
        "edges": [
            {
                "edge_id": "EDGE-1",
                "edge_type": "COVERS",
                "source_id": "ARTICLE-1",
                "target_id": "EVENT-1",
                "confidence": 1.0,
            },
            {
                "edge_id": "EDGE-2",
                "edge_type": "CONTAINS_STATEMENT",
                "source_id": "ARTICLE-1",
                "target_id": "STATEMENT-1",
                "confidence": 1.0,
            },
        ],
    }
    out = adapt_to_schema(
        article=article,
        kg=kg,
        classification={"big_cls": "경제", "small_cls": "x", "region_cls": "y", "topic": "경제"},
        event_embeddings={},
        embedding_model="nlpai-lab/KURE-v1",
        embedding_dim=3,
    )
    statement = next(n for n in out["nodes"] if "Statement" in n["labels"])
    assert statement["properties"]["text"] == "다음 달부터 신청을 받는다고 말했다"
    assert statement["properties"]["statementType"] == "FORECAST"
    event = next(n for n in out["nodes"] if "Event" in n["labels"])
    assert event["properties"]["title"] == "서울시가 주거 지원을 확대했다"


def test_postprocess_merges_entity_and_drops_noise(tmp_path: Path):
    nodes = [
        {"labels": ["Entity"], "properties": {"nodeId": "E1", "canonicalName": "그"}},
        {"labels": ["Entity"], "properties": {"nodeId": "E2", "canonicalName": "민주당"}},
        {"labels": ["Entity"], "properties": {"nodeId": "E3", "canonicalName": "민주당"}},
        {"labels": ["Event"], "properties": {"nodeId": "V1", "title": "a"}},
    ]
    edges = [
        {
            "edgeId": "x1",
            "type": "MENTIONS",
            "startNodeId": "A1",
            "endNodeId": "E1",
            "properties": {},
        },
        {
            "edgeId": "x2",
            "type": "ACTOR",
            "startNodeId": "V1",
            "endNodeId": "E2",
            "properties": {},
        },
        {
            "edgeId": "x3",
            "type": "ACTOR",
            "startNodeId": "V1",
            "endNodeId": "E3",
            "properties": {},
        },
    ]
    d = tmp_path
    (d / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n, ensure_ascii=False) for n in nodes), encoding="utf-8"
    )
    (d / "edges.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in edges), encoding="utf-8"
    )
    report = postprocess_bundle(d, backup=False)
    out_nodes = [
        json.loads(line)
        for line in (d / "nodes.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ent_ids = {n["properties"]["nodeId"] for n in out_nodes if "Entity" in n["labels"]}
    assert "E1" not in ent_ids
    assert len(ent_ids) == 1
    assert ent_ids <= {"E2", "E3"}
    assert report["noise_entities_dropped"] == 1
    assert report["entity_merge"]["entities_merged_away"] == 1
