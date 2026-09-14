"""Unit tests that do not require model weights."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from starlight_ai.adapter.neo4j_schema import adapt_to_schema
from starlight_ai.device import resolve_device
from starlight_ai.preprocess import preprocess_content
from starlight_ai.topic_map import topic_name_ko


def test_preprocess_keeps_sentence_lines():
    raw = "짧은\n서울시는 지원을 확대한다고 발표했다.\n@spam"
    out = preprocess_content(raw)
    assert "서울시는" in out
    assert "@spam" not in out


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
    time_n = next(n for n in out["nodes"] if "Time" in n["labels"])
    assert time_n["properties"]["timeKey"] == "2026-09-08"
    edge_types = {e["type"] for e in out["edges"]}
    assert "CONTAINS_STATEMENT" in edge_types
    assert "MEMBER_OF_EVENT" not in edge_types
    assert "PUBLISHED_BY" not in edge_types
