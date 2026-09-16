# FastAPI 연동 가이드 (상주 AI 워커)

이 문서는 **FastAPI 담당자**가 상주 `ai-worker`의 `/internal/v1/articles/analyze`를 호출할 때 쓰는 계약서다.
AI 쪽은 **Neo4j MERGE / Spring API를 구현하지 않는다.** 스키마에 가까운 JSON만 반환한다.

---

## 1. 역할 분담

| 담당 | 하는 일 |
|------|---------|
| **AI (`ai/`)** | 기사 1건 → KG 추출 + Topic(대분류) + Event 임베딩 → **스키마형 JSON** |
| **FastAPI** | 내부 API로 AI 호출, 요청/응답 DTO, 타임아웃·에러 코드, (합의 시) Neo4j 적재 호출 |
| **Spring** | 수집·`PUBLISHED_BY`(언론사) 등 크롤 메타, MySQL 기사 상태, AI/FastAPI 트리거 |

AI가 **하지 않는 것**

- `PUBLISHED_BY` 엣지 생성 (Spring이 보유)
- Story / User 그래프
- 교차 기사 Event 병합 (`SAME_EVENT` 자동 병합)
- Neo4j 직접 WRITE (적재는 백엔드)

---

## 2. 디렉터리 구조

```text
ai/
├── README.md                 # CPU 환경·volume
├── FASTAPI_연동.md           # 본 문서
├── requirements-cpu.txt
├── Dockerfile
├── starlight_ai/             # import 가능한 코어 패키지
│   ├── __init__.py           # process_article, ArticleAnalyzer export
│   ├── server.py             # 상주 HTTP 워커와 readiness
│   ├── pipeline.py           # 단건 오케스트레이션
│   ├── preprocess.py         # 본문 전처리
│   ├── models/               # 래퍼만 (로드/추론)
│   │   ├── kpf_classifier.py # Topic용 대/소/지역 분류
│   │   ├── kg_extractor.py   # ArticleLocalKGPipeline (HF 번들)
│   │   └── event_embedder.py # nlpai-lab/KURE-v1 (server volume, 1024-d)
│   ├── adapter/
│   │   └── neo4j_schema.py   # V2 KG + Topic + embedding → 서비스 스키마 JSON
└── test_pipeline/            # 단건 스모크 (기존 → 코어 호출로 이행)
```

FastAPI는 코어를 직접 import하지 않고 **같은 Compose 네트워크의 AI 워커를 HTTP로 호출**한다.
따라서 FastAPI 이미지에 torch, 모델 가중치, `starlight_ai` 패키지를 넣지 않는다.

```text
Spring → backend-fastapi:8000/internal/v1/articles/analyze
       → ai-worker:8100/internal/v1/articles/analyze
       → backend-fastapi가 결과를 Neo4j에 반영
```

---

## 3. 파이프라인 단계 (AI가 짤 코드)

```text
입력 Article
  → (1) preprocess          본문 정리 (기존 test_pipeline과 동일 계열)
  → (2) KPF classify        big/small/region → Topic 힌트 ("경제" 등)
  → (3) KG extract          HF ArticleLocalKGPipeline (public v2)
  → (4) Event embed         각 EVENT 문장 → 1024-d 벡터 (KURE-v1)
  → (5) schema adapter      서비스 Neo4j에 가까운 nodes/edges JSON
  → 반환 dict
```

| 단계 | 모델 / 소스 | 산출 |
|------|-------------|------|
| 분류 | `KPF/KPF-bert-cls1/2/3` + `jinmang2/kpfbert` | Topic 문자열(대분류 `nameKo`) |
| KG | `sysy9292/kf-deberta-base-kg-extractor` V2 + base `kakaobank/kf-deberta-base` | 5종 노드 · 7종 엣지 |
| 임베딩 | `nlpai-lab/KURE-v1` (volume) | Event당 `embedding` / `embeddingModel` (1024-d) |

KG 공식 공개 엣지(모델 카드):  
`COVERS`, `CONTAINS_STATEMENT`, `MENTIONS`, `ACTOR`, `TARGET`, `PLACE`, `OCCURRED_ON`  
(`ASSERTED_BY` / `ABOUT` / `CAUSES` 등은 릴리스에서 NOT_RUN → 안 나옴)

---

## 4. 입력 계약

FastAPI → AI 코어로 넘길 최소 필드.

| 필드 | 필수 | 설명 |
|------|------|------|
| `article_id` | ✅ | 호출측 ID (문자열). MySQL PK를 문자열로 넣어도 됨 |
| `content` | ✅ | 본문 (offset 기준 원문) |
| `title` | 권장 | 제목 |
| `published_at` | 권장 | ISO 8601 권장 |
| `mysql_article_id` | 권장 | 있으면 Article 노드 `mysqlArticleId`에 그대로 반영 |
| `source` | 선택 | 출처 라벨 (PUBLISHED_BY는 AI가 안 만듦) |

별칭은 KG 번들 관례를 따를 수 있다 (`raw_text`→content 등). **canonical은 위 표.**

---

## 5. 출력 계약 (스키마에 가까운 JSON)

단건 분석 결과의 **논리 형태**다. 필드명은 구현 시 Pydantic으로 고정하고, 여기와 어긋나면 본 문서를 수정한다.

### 5.1 최상위

```json
{
  "schema_version": "starlight-article-analyze-v1",
  "status": "OK",
  "article": { "...": "입력 에코 + 정규화 메타" },
  "classification": {
    "big_cls": "경제",
    "small_cls": "취업_창업",
    "region_cls": "지역일반",
    "topic": "경제"
  },
  "nodes": [],
  "edges": [],
  "warnings": [],
  "meta": {
    "kg_schema_version": "articlelocal-kg-public-v2",
    "embedding_model": "nlpai-lab/KURE-v1",
    "embedding_dim": 1024,
    "device": "cpu"
  }
}
```

- `classification.topic`: 서비스 Topic `nameKo`에 맞춘 한글 대분류.  
  `IT_과학` → `IT·과학` 등 정규화 포함.  
- FastAPI/적재 측이 `CLASSIFIED_AS`를 만들 때 이 문자열을 쓰면 된다.  
  (AI가 edges에 `CLASSIFIED_AS`를 **넣을지**는 구현 옵션; 넣지 않아도 `classification.topic`은 항상 제공한다.)

### 5.2 nodes[]

서비스 Neo4j Label·property 이름을 **최대한** 따른다.

| labels | 필수에 가까운 properties |
|--------|-------------------------|
| `["Article"]` | `nodeId`, `title`, `publishedAt`, (`mysqlArticleId`) |
| `["Event"]` | `nodeId`, `title`, `embedding`, `embeddingModel` |
| `["Entity", "Person" \| "Company" \| …]` | `nodeId`, `canonicalName`, `entityType` |
| `["Statement"]` | `nodeId`, `text`, `statementType` |
| `["Time"]` (+ `Year`/`Month`/`Day` 가능 시) | `nodeId`, `value` 또는 `timeKey`, `granularity` |

- KG V2의 `ENTITY` 한 종류 → `entityType` 보고 **Entity + 세부 Label**로 펼친다.  
- Event 본문: 모델 `text` / canonical → 서비스 **`title`**.  
- `nodeId`: 단건 내 안정 문자열 (UUID 또는 번들 id). 전역 merge는 적재 담당.

### 5.3 edges[]

```json
{
  "edgeId": "...",
  "type": "COVERS",
  "startNodeId": "...",
  "endNodeId": "...",
  "properties": { "confidence": 0.9 }
}
```

| type | from → to | AI 제공 |
|------|-----------|---------|
| `COVERS` | Article → Event | ✅ |
| `MENTIONS` | Article → Entity | ✅ |
| `CONTAINS_STATEMENT` | Article → Statement | ✅ |
| `ACTOR` / `TARGET` / `PLACE` | Event → Entity | ✅ |
| `OCCURRED_ON` | Event → Time | ✅ |
| `CLASSIFIED_AS` | Article\|Event → Topic | 선택 (없어도 `classification.topic` 있음) |
| `PUBLISHED_BY` | Article → NewsOrg | ❌ Spring |

없는 엣지 = 해당 lane 미실행/미해결일 수 있음. **부정(없다)로 단정하지 말 것** (모델 카드와 동일).

### 5.4 Event 임베딩

- 모델: **`nlpai-lab/KURE-v1`** (서버 `ai-cpu-models` 캐시와 동일)
- 차원: **1024**, L2 정규화 (`normalize_embeddings=True`)
- property: `embedding: number[]`, `embeddingModel: string`
- `HF` 캐시는 분류/KG와 같은 `hf_cache`(` /models/cache/hub`)를 사용한다
- **LOCAL_EVENT는 노드/임베딩 대상에서 제외** (V2 public kind = `EVENT`만)
- 용도: 적재·이후 유사 검색. 단건 API 안에서 교차 기사 병합하지 않음

### 5.5 Entity / Time 주의

- `PERSON` → `Entity:Person`, `LOCATION` → `Entity:Location`
- `ORGANIZATION` → `Entity`만 + `entityType=ORGANIZATION` (Company/GovernmentAgency 세분은 적재·후처리)
- Time: `value`/`granularity` 외에 **`timeKey`를 value로 채움** (UNIQUE 제약용)

### 5.6 없는 것

- `PUBLISHED_BY` — Spring
- KLUE-RE 등 별도 Relation 모델 — **없음**. Role/관계는 KG 번들 엣지에만 의존
- `ASSERTED_BY` / `ABOUT` / `CAUSES` — KG 릴리스 NOT_RUN

---

## 6. FastAPI에서 붙이는 방법 (체크리스트)

1. **런타임 분리**: `ai-worker`만 AI 이미지와 `ai-cpu-models:/models:ro`를 사용한다.
2. **직접 import 금지**: FastAPI는 `AI_BASE_URL`을 통해 내부 HTTP로 호출한다.
3. **워커 상주**: AI 프로세스 기동 시 모델을 1회 로드하고 같은 `ArticleAnalyzer`를 재사용한다.
4. **호출**: `POST {AI_BASE_URL}/internal/v1/articles/analyze`.
5. **응답**: 위 JSON을 그대로 반환하거나, FastAPI `response_model`로 감싼다.  
6. **에러**  
   - 입력 불량 → `INVALID_ARTICLE` (기존 exceptions 경로와 맞춤)  
   - 추론 실패 → `EXTRACTION_FAILED`  
7. **적재**: nodes/edges(+ topic, embedding)를 Neo4j MERGE하는 코드는 FastAPI/적재 담당.  
8. **PUBLISHED_BY**: AI 응답에 없어도 Spring 메타로 별도 MERGE.

### 연결 위치

```text
backend/fastapi/app/articles/
  router.py   → POST /articles/analyze
  service.py  → AI 워커 HTTP 호출 후 repository 적재
  schemas.py  → Spring 요청/최종 응답 계약
```

---

## 7. 환경 변수

### AI 워커

| 변수 | 의미 | 기본 |
|------|------|----------------|
| `KG_MODEL_DIR` | KG 번들 루트 | `/models/artifacts/kg-extractor` |
| `ARTICLELOCAL_HF_CACHE` / HF cache | 베이스·임베딩 캐시 | `/models/cache/hub` |
| `HF_HUB_OFFLINE` | `1` 권장 (서버) | 재다운로드 금지 |
| `STARLIGHT_AI_DEVICE` | `cpu` / `cuda` / `auto` | 서버는 `cpu` |

임베딩 모델은 volume의 `nlpai-lab/KURE-v1`을 쓴다. 오버라이드: `STARLIGHT_EMBEDDING_MODEL`.

### Backend FastAPI

| 변수 | 의미 | 기본 |
|------|------|------|
| `AI_BASE_URL` | 상주 AI 워커 주소 | `http://ai-worker:8100` |
| `AI_CONNECT_TIMEOUT_SECONDS` | 연결 제한 | `3` |
| `AI_REQUEST_TIMEOUT_SECONDS` | 기사 1건 추론 제한 | `150` |


---

## 8. 구현 상태

| 항목 | 상태 |
|------|------|
| 본 연동 계약 문서 | ✅ |
| `starlight_ai` 패키지 / `process_article` | ✅ `ai/starlight_ai/` |
| Event 임베딩 단계 | ✅ |
| Neo4j 스키마 어댑터 | ✅ |
| Topic(`nameKo`) 정규화 | ✅ (`IT_과학`→`IT·과학`) |
| 상주 AI HTTP 워커 | ✅ `starlight_ai/server.py` |
| FastAPI HTTP 연결 | ✅ `backend/fastapi/app/articles/service.py` |
| Neo4j MERGE | ✅ `backend/fastapi/app/articles/repository.py` |

### AI 워커 직접 확인

```bash
curl http://127.0.0.1:8100/ready
curl -X POST http://127.0.0.1:8100/internal/v1/articles/analyze \
  -H 'Content-Type: application/json' \
  -d '{"article_id":"930001","mysql_article_id":930001,"title":"...","content":"...","published_at":"2026-09-08T09:00:00+09:00"}'
```

운영 Compose에서는 8100 포트를 호스트에 공개하지 않으므로 컨테이너 네트워크 안에서 확인한다.

### 디바이스 주의

| 환경 | 설정 |
|------|------|
| **서버 (EC2)** | `STARLIGHT_AI_DEVICE=cpu` 또는 `device="cpu"` — GPU 없음 |
| **로컬** | `auto`(CUDA 있으면 사용) 또는 `cuda` |

CLI 스모크: `python -m starlight_ai.cli --help` (`ai/`를 PYTHONPATH에 둔 뒤).

---

## 9. 문의 시 보면 좋은 것

- KG 모델 카드: `sysy9292/kf-deberta-base-kg-extractor` (Release V2, `articlelocal-kg-public-v2`)
- 서비스 Neo4j 제약: `backend/fastapi/migrations/neo4j/V1__initial_graph_schema.cypher`
- 기존 CPU 스모크: `ai/test_pipeline/README.md`
