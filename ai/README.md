# AI CPU 추론 환경

서버에서 **Docker 이미지 + named volume**으로 CPU 전용 추론 런타임을 구성했다.
GPU는 없다. 모델 가중치는 Git/이미지에 넣지 않고 volume에만 둔다.

## 구성 요약

| 구분 | 내용 |
|------|------|
| 호스트 | EC2, CPU 4코어, RAM 15GB, Swap 없음, GPU 없음 |
| 런타임 이미지 | `ai-cpu:dev` (`ai/Dockerfile`) |
| 베이스 | `python:3.12-slim` |
| 주요 패키지 | torch **2.6.0+cpu**, transformers **4.51.3**, huggingface-hub **0.30.2** |
| 모델 volume | `ai-cpu-models` → 컨테이너 `/models` |
| 코드 | Git `ai/` (가중치 제외) |
| Compose 본편 | **아직 미편입** (단독 `docker run`으로 검증) |

### volume 레이아웃

```text
ai-cpu-models (/models)
├── artifacts/kg-extractor/   # KG 번들 (config, runtime, weights…)
└── cache/hub/                # HF hub 캐시 (models--*)
    ├── models--kakaobank--kf-deberta-base
    ├── models--jinmang2--kpfbert
    ├── models--KPF--KPF-bert-cls1
    ├── models--KPF--KPF-bert-cls2
    └── models--KPF--KPF-bert-cls3
```

디스크 합계 약 **6.1GB**. 추론은 `HF_HUB_OFFLINE=1` / `local_files_only`로 **재다운로드하지 않는다**.

### 이미지 빌드

```bash
cd /home/ubuntu/S15P21E206/ai
sudo docker build -t ai-cpu:dev .
```

### 설계 의도

- **코드 = Git**, **환경 = 이미지**, **모델 = volume**
- master CD의 앱 재시작과 AI 모델 수명 주기를 분리 (본편 compose 편입은 추후)
- 컨테이너 삭제·이미지 재빌드해도 volume만 유지하면 모델을 다시 받을 필요 없음
- `down -v`로 volume을 지우면 모델도 삭제되므로 주의

## 테스트 (`test_pipeline/`)

합성 기사 1건으로 **전처리 → KPF 분류 3종 → KG 추출**이 CPU에서 도는지 확인한다.
상세 실행법·결과 해석은 [test_pipeline/README.md](test_pipeline/README.md)를 본다.

### 실행 방법

```bash
sudo docker run --rm \
  -v ai-cpu-models:/models \
  -v /home/ubuntu/S15P21E206/ai/test_pipeline:/work \
  -w /work \
  -e HF_HUB_OFFLINE=1 \
  -e TRANSFORMERS_OFFLINE=1 \
  ai-cpu:dev \
  python pipeline.py
```

기본 경로(컨테이너):

- KG: `/models/artifacts/kg-extractor`
- HF cache: `/models/cache/hub`

### 측정 결과 (이 서버, 2026-09-10)

합성 기사: 「서울시, 청년 주거 지원 확대」 (`cpu-synthetic-001`)

| 항목 | 결과 |
|------|------|
| 상태 | **PASSED** (구조 검증 성공, 분류 정확도 보장은 아님) |
| 분류 | 경제 / 취업_창업 / 지역일반 |
| KG | 9 nodes, 9 edges, validation PASS |
| `docker run`마다 E2E | 약 **12.7–13.3초** (로딩 포함) |

로딩 vs 순수 추론을 나눈 측정(동일 기사, 1회):

| 구간 | 시간 |
|------|------|
| KPF 로딩 | ~3.4초 |
| KPF 추론 | ~0.4초 |
| KG 로딩 | ~3.9초 |
| KG 추론 | ~4.5초 |
| **로딩 합** | **~7.3초** |
| **순수 추론 합** | **~4.9초** |

지금 `pipeline.py`는 매 실행마다 컨테이너·프로세스를 새로 띄우고, KPF를 쓴 뒤 내린 다음 KG를 올린다.
그래서 **다음 실행도 비슷한 13초 전후**가 정상이다.
워커를 상주시키고 모델을 RAM에 유지하면 로딩이 “빨라지는” 것이 아니라 **이후 기사에서 로딩을 생략**할 수 있다.

### 메모리·상주 가능성

| 항목 | 관측/추정 |
|------|-----------|
| 호스트 available | 약 **11GB** (총 15GB, swap 없음) |
| 기존 서비스 (MySQL, Neo4j, Spring 등) | 대략 **1.3GB**대 |
| 단건 추론 중 AI 컨테이너 cgroup peak | 약 **0.5GB** (순차 로드·mmap/페이지 캐시 영향으로 과소평가 가능) |
| 판단 | **상시 워커 운영은 가능해 보임**. swap이 없어 OOM 여유는 실측 후 limit 권장 |

운영 가정(15–30분 주기, 파이프라인 투입 &lt;200건)과도 맞는 편이다.
긴 기사·동시 요청·KPF+KG 동시 상주는 peak가 더 커질 수 있으니 별도 측정이 필요하다.

## FastAPI 연동 (계약)

AI는 **`ai/` 코어만** 제공한다. FastAPI·Neo4j 적재·`PUBLISHED_BY`는 백엔드 담당.

→ 입출력·역할 분담·체크리스트: **[`FASTAPI_연동.md`](FASTAPI_연동.md)**

### 코어 패키지 (`starlight_ai/`)

```text
기사 1건
  → 전처리 → KPF 분류(Topic) → HF KG → Event 임베딩
  → 스키마형 JSON (nodes/edges + classification.topic + Event.embedding)
```

- import: `from starlight_ai import ArticleAnalyzer, process_article`
- **서버는 CPU만** → `STARLIGHT_AI_DEVICE=cpu` (로컬만 `auto`/`cuda`)
- 단위 테스트: `python -m pytest ai/tests -q` (모델 불필요)
- 로컬 스모크 예:

```powershell
cd ai
$env:STARLIGHT_AI_DEVICE="auto"   # 서버에서는 cpu
$env:PYTHONPATH="."
python -m starlight_ai.cli `
  --kg-dir "C:\Users\SSAFY\Desktop\gnews_api_test\artifacts\kg-extractor" `
  --hf-cache "C:\Users\SSAFY\Desktop\gnews_api_test\.cache\huggingface\hub" `
  --input test_pipeline\article.json `
  --output test_pipeline\starlight_result.json
```

## 아직 하지 않은 것

- 본편 `docker-compose.yml`에 AI 서비스 편입
- FastAPI `articles/analyze` stub 연결 (FastAPI 담당)
- Neo4j MERGE (적재 담당)
- 모델 revision을 `cpu_settings` 수준으로 문서 외 추가 고정 관리

## 관련 파일

- [`FASTAPI_연동.md`](FASTAPI_연동.md) — FastAPI 담당용 입출력 계약
- [`Dockerfile`](Dockerfile) — CPU 런타임 이미지
- [`requirements-cpu.txt`](requirements-cpu.txt) — torch 제외 pip 의존성
- [`test_pipeline/`](test_pipeline/) — 최소 추론 확인 예제
