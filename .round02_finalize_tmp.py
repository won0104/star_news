"""Round 02 검토 이력, microbatch final, 50건 통합본을 일관되게 생성한다."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\SSAFY\data\SSAFY_ARTICLE_2024H1")
ROUND_DIR = ROOT / "round-02"
GENERATOR_DIR = ROUND_DIR / "generator" / "microbatches"
REVIEW_DIR = ROUND_DIR / "reviewer" / "microbatches"
FINAL_DIR = ROUND_DIR / "adjudicator" / "microbatches"
DELIVERY_DIR = ROUND_DIR / "delivery"
MANIFEST_PATH = ROUND_DIR / "input_manifest.json"
MICROBATCH_IDS = ["01", "02", "03", "04", "05"]
LABEL_FIELDS = [
    "entity_mentions",
    "entity_clusters",
    "time_mentions",
    "event_frames",
    "statements",
    "event_clusters",
    "hard_relations",
]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def article_id(number: int) -> str:
    return f"ssafy-news-2024h1-{number}"


def decision(
    suffix: str,
    primary: int,
    affected: list[int],
    family: str,
    initial: str,
    user: str,
    final: str,
    decision_type: str,
    reason: str,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "decision_id": suffix,
        "article_id": article_id(primary),
    }
    if len(affected) > 1:
        item["affected_article_ids"] = [article_id(value) for value in affected]
    item.update(
        {
            "family": family,
            "initial_decision": initial,
            "user_decision": user,
            "final_decision": final,
            "decision_type": decision_type,
            "reason": reason,
        }
    )
    return item


REVIEW_DECISIONS: dict[str, list[dict[str, Any]]] = {
    "02": [
        decision(
            "round-02-m02-review-01", 65395, [65395, 70146],
            "EVENT_STATEMENT_BOUNDARY",
            "'세계적으로 인정받은' 표현을 등록 Event와 중복되는 Event로 볼지 검토",
            "평가 표현으로 보아 Statement로 유지하고 뒤의 희귀성 설명도 Statement로 처리",
            "두 표현을 EVALUATION Statement로 유지하고 등록 Event와 혼합하지 않음",
            "USER_MODIFIED",
            "공적 등록 행위와 기자의 가치 평가는 독립적으로 성립한다.",
        ),
        decision(
            "round-02-m02-review-02", 547301, [547301, 388257, 553657, 391546],
            "EPISTEMIC_CAUSALITY",
            "니콜라 주가 변동 설명을 모두 hard CAUSES로 연결하는 방안 검토",
            "사실로 단정된 인과만 CAUSES로 두고 기자의 해석·추정 표현은 Statement로 보존",
            "'때문으로 보인다' 등 완화된 설명에는 CAUSES를 만들지 않고, 직접 단정된 '때문이다/따라' 사례만 CAUSES로 유지",
            "GUIDELINE_CLARIFICATION",
            "기사-local factual relation과 인과 해석의 epistemic status를 구분한다.",
        ),
        decision(
            "round-02-m02-review-03", 388257, [388257, 553657, 391546],
            "EVENT_FORECAST_BOUNDARY",
            "충전소 설치 발표와 실제 미래 설치를 하나의 사건으로 처리",
            "발표는 실제 Event, 아직 실행되지 않은 설치는 FORECAST로 구분",
            "발표 Event는 유지하고 내포된 충전소 설치 계획을 별도 FORECAST로 추가; 같은 발표를 가리키는 mention은 하나의 event cluster로 묶음",
            "USER_MODIFIED",
            "발표 행위는 발생했지만 발표 내용의 설치는 미래 양태다.",
        ),
    ],
    "03": [
        decision(
            "round-02-m03-review-01", 555588, [555588, 393242, 561763, 397773],
            "EPISTEMIC_CAUSALITY",
            "주가 변동 기사에 나타난 인과 설명을 동일한 hard CAUSES 정책으로 처리",
            "단정 표현에는 CAUSES를 유지하고 '풀이된다/보인다'처럼 기자 의견인 경우 제거",
            "직접적인 '발언으로/소식으로/때문이다' 사례에는 CAUSES를 유지하고 완화된 해석은 CLAIM과 ABOUT으로만 보존",
            "GUIDELINE_CLARIFICATION",
            "문법적 선후가 아니라 기사에서 확정한 인과의 epistemic status를 기준으로 한다.",
        ),
        decision(
            "round-02-m03-review-02", 439558, [439558, 176248, 260635],
            "ASSERTOR_RESOLUTION",
            "청와대 인사 소환 임박 관측의 assertor를 생략하거나 내부 명제 주체로 처리",
            "문맥상 실제 관측 주체인 '법조계 안팎'을 assertor로 확정",
            "법조계 안팎을 span 기반 assertor로 기록하고 내부 명제의 청와대 인사와 구분",
            "USER_MODIFIED",
            "Assertor는 전망 내용의 대상이 아니라 실제 전망을 제시한 출처다.",
        ),
        decision(
            "round-02-m03-review-03", 260635, [260635],
            "EVENT_FORECAST_BOUNDARY",
            "압수물 분석 방침을 분석 Event로도 생성",
            "실행되지 않은 계획은 Event가 아니라 FORECAST로 처리",
            "분석 Event를 제거하고 검찰의 분석·확인 방침을 FORECAST로만 유지",
            "USER_MODIFIED",
            "기사 기준시점에 실행되지 않은 계획을 실제 occurrence로 승격하지 않는다.",
        ),
        decision(
            "round-02-m03-review-04", 210757, [210757, 675190],
            "HARD_RELATION",
            "진술거부와 조사 조기 종료를 독립 사건으로만 유지",
            "진술거부 때문에 조사가 일찍 끝났다는 직접 인과를 CAUSES로 연결",
            "진술거부 Event에서 조사 조기 종료 Event로 CAUSES를 추가",
            "USER_MODIFIED",
            "원문이 진술거부를 조사 종료의 직접 원인으로 제시한다.",
        ),
        decision(
            "round-02-m03-review-05", 210757, [210757, 675190],
            "RETROSPECTIVE_FORECAST",
            "실현되지 않은 과거 질문 계획을 결과에 맞춰 제거하거나 Event로 변경",
            "기사에 과거 시점의 계획으로 명시된 내용은 가이드라인대로 FORECAST로 유지",
            "질문 계획은 FORECAST로 보존하고 실제 질문 Event를 추정해 추가하지 않음",
            "USER_CONFIRMED",
            "FORECAST는 기사 작성 시점의 미래에만 한정되지 않고 명시된 계획의 양태를 보존한다.",
        ),
        decision(
            "round-02-m03-review-06", 439558, [439558, 176248, 260635],
            "ASSERTOR_REPRESENTATION",
            "Assertor를 hard relation 배열로 이동할지 검토",
            "골드 JSON에서는 Statement 내부 assertor 객체를 그대로 유지",
            "스키마의 assertor.entity_id 표현을 유지하고 그래프 적재 시 ASSERTED_BY 관계로 변환 가능하도록 함",
            "GUIDELINE_CLARIFICATION",
            "주석 교환 형식과 Neo4j 물리 저장 형식은 분리되며 현 Gold schema를 임의 변경하지 않는다.",
        ),
    ],
    "04": [
        decision(
            "round-02-m04-review-01", 441548, [441548],
            "HARD_RELATION",
            "진술거부와 조사 조기 종료를 독립 Event로만 처리",
            "두 사건의 직접 인과를 CAUSES로 연결",
            "진술거부 Event에서 조사 조기 종료 Event로 CAUSES를 추가",
            "USER_MODIFIED",
            "원문이 진술거부로 인해 조사가 일찍 끝났다고 명시한다.",
        ),
        decision(
            "round-02-m04-review-02", 151262, [151262, 201099, 614361, 423080],
            "HARD_RELATION",
            "준결승 승리와 결승 진출, 준결승 패배와 결승 진출 실패를 선후 관계로만 유지",
            "승패가 다음 단계 진출 여부를 결정하므로 각각 CAUSES로 연결",
            "준결승 승리→결승 진출 및 준결승 패배→결승 진출 실패 CAUSES를 추가·유지",
            "USER_MODIFIED",
            "토너먼트 규칙상 해당 경기 결과가 다음 라운드 진출 여부의 직접 조건이다.",
        ),
        decision(
            "round-02-m04-review-03", 620677, [620677, 426280],
            "SUBEVENT_STRUCTURE",
            "4강전의 두 게임 결과를 전체 4강전 승리와 독립된 Event로만 유지",
            "각 게임 승리를 4강전 승리의 하위 사건으로 연결",
            "1게임 승리와 2게임 승리 각각에서 4강전 승리로 SUBEVENT_OF를 추가",
            "USER_MODIFIED",
            "각 게임은 경계가 있는 상위 경기의 구성 사건이다.",
        ),
        decision(
            "round-02-m04-review-04", 151262, [151262, 201099, 614361, 423080, 620677, 426280],
            "EVENT_FORECAST_EVALUATION_BOUNDARY",
            "올림픽 실전 점검과 순항 표현을 하나의 평가로 처리",
            "예정된 실전 점검은 FORECAST, '순항'은 별도 EVALUATION으로 분리; 후속 기사에서 실제 참가 중이면 Event로 처리",
            "싱가포르 기사에서는 실전 점검 FORECAST와 순항 EVALUATION을 분리하고, 인도네시아오픈 참가 기사에서는 실제 실전 점검 Event를 유지",
            "USER_MODIFIED",
            "기사 기준시점의 실행 여부와 평가 명제의 독립 성립 여부를 함께 반영한다.",
        ),
    ],
    "05": [
        decision(
            "round-02-m05-review-01", 76148, [76148, 76637, 517931, 276885],
            "ATTRIBUTION_EVENT_FORECAST_BOUNDARY",
            "발표·브리핑 예정 문장을 FORECAST로만 처리",
            "진행·행사 내용은 FORECAST지만 이를 밝혔다고 한 행위는 실제 Event로 분리",
            "실제 발표/고지 Event와 내포된 회의·브리핑·감독 발표 FORECAST를 분리",
            "USER_MODIFIED",
            "실제 발생한 attribution carrier와 아직 실현되지 않은 명제의 양태가 다르다.",
        ),
        decision(
            "round-02-m05-review-02", 517931, [517931, 276885],
            "ASSERTOR_RESOLUTION",
            "브리핑 진행 전망의 내부 주체인 정해성 위원장을 assertor로 처리",
            "실제 발표 출처인 대한축구협회(KFA)를 assertor로 사용",
            "KFA Entity를 FORECAST의 assertor로 연결하고 내부 명제 주체와 구분",
            "GUIDELINE_CLARIFICATION",
            "Assertor는 내포 명제의 행위자가 아니라 그 명제를 기사에 제시한 실제 출처다.",
        ),
        decision(
            "round-02-m05-review-03", 173963, [173963, 438060, 295264],
            "ATTRIBUTION_EVENT_FORECAST_BOUNDARY",
            "거부권 행사 예고를 FORECAST로만 처리",
            "미래 거부권 행사는 FORECAST지만 예고한 행위는 실제 Event로 분리",
            "대통령실의 예고 Event와 거부권 행사 FORECAST를 각각 유지",
            "USER_MODIFIED",
            "예고는 기사 기준시점에 발생했고 예고된 거부권 행사는 아직 실현되지 않았다.",
        ),
        decision(
            "round-02-m05-review-04", 670430, [670430, 176720],
            "HARD_RELATION",
            "보석 허가 결정, 석방, 불구속 재판을 연쇄 CAUSES로 연결",
            "보석 허가 결정에서 석방으로만 직접 CAUSES를 부여하고 단순 후속 상태는 확장하지 않음",
            "보석 허가 결정→석방 CAUSES를 유지하고 석방→불구속 재판 관계는 생성하지 않음",
            "USER_CONFIRMED",
            "직접 근거가 있는 인과만 보존하고 시간적·절차적 후속을 자동 인과로 확장하지 않는다.",
        ),
    ],
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_reviews() -> None:
    for microbatch_id, decisions in REVIEW_DECISIONS.items():
        path = REVIEW_DIR / f"review-{microbatch_id}.json"
        review = json.loads(path.read_text(encoding="utf-8"))
        review["human_policy_reviewed"] = True
        review["review_decisions"] = decisions
        review["decision_count"] = len(decisions)
        review["decision_type_counts"] = dict(
            sorted(Counter(item["decision_type"] for item in decisions).items())
        )
        write_json(path, review)


def validate_spans(value: Any, content: str, location: str, issues: list[str]) -> None:
    if isinstance(value, dict):
        if {"text", "start", "end"}.issubset(value):
            start = value.get("start")
            end = value.get("end")
            text = value.get("text")
            if isinstance(start, int) and isinstance(end, int) and isinstance(text, str):
                if start < 0 or end < start or end > len(content) or content[start:end] != text:
                    issues.append(f"{location}: exact span 불일치 ({start}, {end}, {text!r})")
        for key, item in value.items():
            validate_spans(item, content, f"{location}.{key}", issues)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_spans(item, content, f"{location}[{index}]", issues)


def validate_references(article: dict[str, Any], issues: list[str]) -> None:
    aid = article["article_id"]
    mention_ids = {item["mention_id"] for item in article["entity_mentions"]}
    entity_ids = {item["entity_id"] for item in article["entity_clusters"]}
    time_ids = {item["time_mention_id"] for item in article["time_mentions"]}
    event_ids = {item["event_id"] for item in article["event_frames"]}
    statement_ids = {item["statement_id"] for item in article["statements"]}
    for cluster in article["entity_clusters"]:
        if not set(cluster["mention_ids"]).issubset(mention_ids):
            issues.append(f"{aid}: entity cluster dangling mention")
    for frame in article["event_frames"]:
        for role_name in ("places", "actors", "targets"):
            for role in frame.get(role_name, []):
                value = role.get("entity_id")
                if value is not None and value not in entity_ids:
                    issues.append(f"{aid}: {frame['event_id']} dangling entity")
        for role in frame.get("times", []):
            value = role.get("time_mention_id")
            if value is not None and value not in time_ids:
                issues.append(f"{aid}: {frame['event_id']} dangling time")
    for statement in article["statements"]:
        assertor = statement.get("assertor")
        if isinstance(assertor, dict):
            value = assertor.get("entity_id")
            if value is not None and value not in entity_ids:
                issues.append(f"{aid}: {statement['statement_id']} dangling assertor")
        for about in statement.get("about", []):
            if about.get("event_id") is not None and about["event_id"] not in event_ids:
                issues.append(f"{aid}: dangling ABOUT event")
            if about.get("statement_id") is not None and about["statement_id"] not in statement_ids:
                issues.append(f"{aid}: dangling ABOUT statement")
            if about.get("entity_id") is not None and about["entity_id"] not in entity_ids:
                issues.append(f"{aid}: dangling ABOUT entity")
    for cluster in article["event_clusters"]:
        if not set(cluster["event_ids"]).issubset(event_ids):
            issues.append(f"{aid}: event cluster dangling event")
    for relation in article["hard_relations"]:
        source = relation["source_event_id"]
        target = relation["target_event_id"]
        if source not in event_ids or target not in event_ids:
            issues.append(f"{aid}: hard relation dangling event")
        if source == target:
            issues.append(f"{aid}: hard relation self-edge")


def powershell_schema_check(data_path: Path, schema_path: Path) -> bool:
    command = (
        f"$ok=(Get-Content -LiteralPath '{data_path}' -Raw | "
        f"Test-Json -SchemaFile '{schema_path}' -ErrorAction SilentlyContinue); "
        "if($ok){exit 0}else{exit 1}"
    )
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def finalize_microbatches(input_by_id: dict[str, dict[str, Any]]) -> None:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    for microbatch_id in MICROBATCH_IDS[1:]:
        proposal_path = GENERATOR_DIR / f"proposal-{microbatch_id}.json"
        proposal_validation_path = GENERATOR_DIR / f"validation-{microbatch_id}.json"
        review_path = REVIEW_DIR / f"review-{microbatch_id}.json"
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        proposal_validation = json.loads(proposal_validation_path.read_text(encoding="utf-8"))
        if proposal_validation.get("status") != "PASS":
            raise ValueError(f"proposal-{microbatch_id} validation이 PASS가 아닙니다.")

        final = deepcopy(proposal)
        final_version = f"ssafy-news-2024h1-round02-microbatch{microbatch_id}-final-r03"
        final_dataset_id = f"ssafy-news-2024h1-round02-microbatch{microbatch_id}-final"
        review_hash = sha256_file(review_path)
        final["version"] = final_version
        final["dataset_id"] = final_dataset_id
        final["processed_dataset"]["path"] = f"../../generator/microbatches/source-{microbatch_id}.jsonl"
        final["processed_dataset"]["version"] = final_version
        final["parent_manifest"] = {
            "path": f"../../reviewer/microbatches/review-{microbatch_id}.json",
            "sha256": review_hash,
        }
        final["provenance"] = {
            "work_name": f"SSAFY News 2024 H1 round-02 Microbatch {microbatch_id} Adjudicated Gold Candidate",
            "method": "MANUAL_SEMANTIC_ANNOTATION_WITH_USER_POLICY_ADJUDICATION",
            "human_reviewed": False,
            "model_predictions_used": False,
            "reviewer_ids": ["codex-primary-self-review", "project-owner"],
            "review_process_manifest": {
                "path": f"../../reviewer/microbatches/review-{microbatch_id}.json",
                "sha256": review_hash,
            },
        }

        final_path = FINAL_DIR / f"final-{microbatch_id}.json"
        write_json(final_path, final)

        schema = json.loads((GENERATOR_DIR / f"schema-{microbatch_id}.json").read_text(encoding="utf-8"))
        schema["$id"] = (
            "https://articlelocal-kg.local/schema/"
            f"ssafy-news-2024h1-round02-microbatch{microbatch_id}-final-r03.schema.json"
        )
        schema["title"] = (
            f"SSAFY News 2024 H1 round-02 Microbatch {microbatch_id} Adjudicated Gold Candidate"
        )
        schema["properties"]["version"]["const"] = final_version
        schema["properties"]["dataset_id"]["const"] = final_dataset_id
        schema["properties"]["provenance"]["properties"]["method"]["const"] = (
            "MANUAL_SEMANTIC_ANNOTATION_WITH_USER_POLICY_ADJUDICATION"
        )
        schema["$defs"]["processedDataset"]["properties"]["version"]["const"] = final_version
        schema_path = FINAL_DIR / f"schema-final-{microbatch_id}.json"
        write_json(schema_path, schema)

        issues: list[str] = []
        if len(final["articles"]) != 10 or len({item["article_id"] for item in final["articles"]}) != 10:
            issues.append("중복 없는 10건 조건 불충족")
        if final["articles"] != proposal["articles"]:
            issues.append("proposal과 final annotation 불일치")
        for article in final["articles"]:
            source = input_by_id[article["article_id"]]
            content = source["content"]
            if sha256_bytes(content.encode("utf-8")) != article["content_sha256"]:
                issues.append(f"{article['article_id']}: content hash 불일치")
            validate_spans(article, content, article["article_id"], issues)
            validate_references(article, issues)
        schema_ok = powershell_schema_check(final_path, schema_path)
        if not schema_ok:
            issues.append("final schema validation 실패")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        validation = {
            "artifact_kind": "MICROBATCH_FINAL_VALIDATION",
            "round_id": "round-02",
            "microbatch_id": microbatch_id,
            "status": "PASS" if not issues else "FAIL",
            "schema_validation": "PASS_POWERSHELL_TEST_JSON" if schema_ok else "FAIL",
            "span_validation": "PASS" if not issues else "FAIL",
            "reference_validation": "PASS" if not issues else "FAIL",
            "article_count": len(final["articles"]),
            "expected_article_count": 10,
            "review_decision_count": review["decision_count"],
            "human_full_reviewed": False,
            "final_sha256": sha256_file(final_path),
            "review_sha256": sha256_file(review_path),
            "proposal_sha256": sha256_file(proposal_path),
        }
        if issues:
            validation["issues"] = issues
        write_json(FINAL_DIR / f"validation-final-{microbatch_id}.json", validation)
        if issues:
            raise RuntimeError(f"microbatch {microbatch_id} final 검증 실패: {issues}")


def assemble_delivery(input_manifest: dict[str, Any]) -> dict[str, Any]:
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    input_articles = input_manifest["articles"]
    input_by_id = {item["article_id"]: item for item in input_articles}
    final_by_id: dict[str, dict[str, Any]] = {}
    source_by_id: dict[str, dict[str, Any]] = {}
    review_decisions: list[dict[str, Any]] = []
    microbatches: list[dict[str, Any]] = []

    for microbatch_id in MICROBATCH_IDS:
        final_path = FINAL_DIR / f"final-{microbatch_id}.json"
        validation_path = FINAL_DIR / f"validation-final-{microbatch_id}.json"
        review_path = REVIEW_DIR / f"review-{microbatch_id}.json"
        source_path = GENERATOR_DIR / f"source-{microbatch_id}.jsonl"
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if validation.get("status") != "PASS":
            raise ValueError(f"microbatch {microbatch_id} final validation이 PASS가 아닙니다.")
        final = json.loads(final_path.read_text(encoding="utf-8"))
        for item in final["articles"]:
            if item["article_id"] in final_by_id:
                raise ValueError(f"중복 final article: {item['article_id']}")
            final_by_id[item["article_id"]] = item
        for line in source_path.read_text(encoding="utf-8").splitlines():
            if line:
                item = json.loads(line)
                source_by_id[item["article_id"]] = item
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review_decisions.extend(review.get("review_decisions", []))
        microbatches.append(
            {
                "microbatch_id": microbatch_id,
                "final_path": str(final_path.relative_to(ROOT)),
                "final_sha256": sha256_file(final_path),
                "review_sha256": sha256_file(review_path),
                "validation_sha256": sha256_file(validation_path),
            }
        )

    expected_ids = [item["article_id"] for item in input_articles]
    if len(expected_ids) != 50 or len(set(expected_ids)) != 50:
        raise ValueError("input manifest가 중복 없는 50건이 아닙니다.")
    if set(final_by_id) != set(expected_ids) or set(source_by_id) != set(expected_ids):
        raise ValueError("manifest, final, source의 article 집합이 다릅니다.")
    ordered_final = [final_by_id[value] for value in expected_ids]
    ordered_source = [source_by_id[value] for value in expected_ids]

    source_path = DELIVERY_DIR / "source-50.jsonl"
    source_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in ordered_source),
        encoding="utf-8",
    )
    review_summary = {
        "artifact_kind": "ROUND_REVIEW_SUMMARY",
        "round_id": "round-02",
        "candidate_status": "PENDING_TEAM_REVIEW",
        "human_full_reviewed": False,
        "human_policy_reviewed": True,
        "article_count": 50,
        "microbatch_count": 5,
        "decision_count": len(review_decisions),
        "review_decisions": review_decisions,
        "microbatches": microbatches,
    }
    review_summary_path = DELIVERY_DIR / "review-summary.json"
    write_json(review_summary_path, review_summary)

    merged_version = "ssafy-news-2024h1-round02-final-r03"
    merged_dataset_id = "ssafy-news-2024h1-round02-final"
    merged = {
        "version": merged_version,
        "dataset_id": merged_dataset_id,
        "annotation_guideline_version": "v3-guideline-r03",
        "processed_dataset": {
            "path": source_path.name,
            "version": merged_version,
            "sha256": sha256_file(source_path),
            "article_count": 50,
            "offset_unit": "unicode-code-point",
            "offset_convention": "0-based-end-exclusive",
        },
        "parent_manifest": {
            "path": "../input_manifest.json",
            "sha256": sha256_file(MANIFEST_PATH),
        },
        "scope": {
            "article_count": 50,
            "original_split": "test",
            "round_ids": ["round-02"],
            "new_rounds_generated": False,
        },
        "provenance": {
            "work_name": "SSAFY News 2024 H1 Round 02 50-Article Adjudicated Gold Candidate",
            "method": "MANUAL_SEMANTIC_ANNOTATION_WITH_USER_POLICY_ADJUDICATION",
            "human_reviewed": False,
            "model_predictions_used": False,
            "reviewer_ids": ["codex-primary-self-review", "project-owner"],
            "review_process_manifest": {
                "path": review_summary_path.name,
                "sha256": sha256_file(review_summary_path),
            },
        },
        "articles": ordered_final,
        "release": {
            "status": "CURATED_RC_WITH_REVIEW_QUEUE",
            "human_review_required_count": 50,
            "review_queue_count": 50,
            "validation_status": "PASS",
        },
    }
    merged_path = DELIVERY_DIR / "ssafy-gold-round02-50-final-r03.json"
    write_json(merged_path, merged)

    schema = json.loads((FINAL_DIR / "schema-final-05.json").read_text(encoding="utf-8"))
    schema["$id"] = "https://articlelocal-kg.local/schema/ssafy-news-2024h1-round02-final-r03.schema.json"
    schema["title"] = "SSAFY News 2024 H1 Round 02 50-Article Adjudicated Gold Candidate"
    schema["properties"]["version"]["const"] = merged_version
    schema["properties"]["dataset_id"]["const"] = merged_dataset_id
    schema["properties"]["articles"]["minItems"] = 50
    schema["properties"]["articles"]["maxItems"] = 50
    schema["properties"]["scope"]["properties"]["article_count"]["const"] = 50
    schema["$defs"]["processedDataset"]["properties"]["version"]["const"] = merged_version
    schema["$defs"]["processedDataset"]["properties"]["article_count"]["const"] = 50
    schema_path = DELIVERY_DIR / "ssafy-gold-round02-50-final-r03.schema.json"
    write_json(schema_path, schema)

    issues: list[str] = []
    for item in ordered_final:
        source = input_by_id[item["article_id"]]
        content = source["content"]
        if sha256_bytes(content.encode("utf-8")) != item["content_sha256"]:
            issues.append(f"{item['article_id']}: content hash 불일치")
        validate_spans(item, content, item["article_id"], issues)
        validate_references(item, issues)
    schema_ok = powershell_schema_check(merged_path, schema_path)
    if not schema_ok:
        issues.append("통합 Gold schema validation 실패")

    counts = {field: sum(len(item[field]) for item in ordered_final) for field in LABEL_FIELDS}
    validation = {
        "artifact_kind": "SSAFY_GOLD_ROUND02_50_DELIVERY_VALIDATION",
        "status": "PASS" if not issues else "FAIL",
        "candidate_status": "PENDING_TEAM_REVIEW",
        "article_count": len(ordered_final),
        "expected_article_count": 50,
        "unique_article_count": len(set(expected_ids)),
        "microbatch_count": 5,
        "microbatch_validations_passed": 5,
        "merged_schema_validation": "PASS_POWERSHELL_TEST_JSON" if schema_ok else "FAIL",
        "span_validation": "PASS" if not issues else "FAIL",
        "reference_validation": "PASS" if not issues else "FAIL",
        "annotation_counts": counts,
        "review_decision_count": len(review_decisions),
        "issues": issues,
        "artifacts": {
            merged_path.name: sha256_file(merged_path),
            schema_path.name: sha256_file(schema_path),
            source_path.name: sha256_file(source_path),
            review_summary_path.name: sha256_file(review_summary_path),
        },
    }
    write_json(DELIVERY_DIR / "validation.json", validation)
    notes = """# SSAFY Gold Round 02 전달 형식

## 상태

- `ssafy-gold-round02-50-final-r03.json`: 사용자 정책 판정이 반영된 50건 통합 Gold 후보
- `source-50.jsonl`: 기사 원문과 출처 메타데이터
- `review-summary.json`: 5개 microbatch의 사용자 정책 검토 이력
- 팀의 전체 재검토 전이므로 `PENDING_TEAM_REVIEW` 및 `human_reviewed=false` 상태를 유지한다.

## 사용 시 주의

- 원문과 주석은 `article_id`로 연결하고 `content_sha256`도 확인한다.
- span은 Unicode code point, 0-based, end-exclusive이며 원문 정규화 시 offset을 함께 재계산해야 한다.
- 이 Round는 동일·후속 story 기사 중심 표본이므로 train/validation/test 분할 시 유사 기사들을 같은 split에 배치한다.
- Assertor는 Gold JSON의 `statement.assertor.entity_id`로 보존하며 그래프 적재 시 `ASSERTED_BY` 관계로 변환할 수 있다.
"""
    (DELIVERY_DIR / "FORMAT_NOTES.md").write_text(notes, encoding="utf-8")
    if issues:
        raise RuntimeError("통합 검증 실패: " + "; ".join(issues))
    return validation


def main() -> None:
    input_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    input_by_id = {item["article_id"]: item for item in input_manifest["articles"]}
    update_reviews()
    finalize_microbatches(input_by_id)
    validation = assemble_delivery(input_manifest)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
