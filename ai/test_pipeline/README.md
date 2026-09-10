# CPU 추론 확인용 최소 예제

서버 AI 환경(`ai-cpu:dev` + volume `ai-cpu-models`)에서
**기사 1건 → KPF 분류 + KG → `result.json`** 이 되는지 확인한다.

전체 환경 구성·메모리·상주 판단은 상위 [ai/README.md](../README.md)를 본다.

## 파일

- `article.json`: 합성 기사 1건
- `pipeline.py`: 전처리, KPF 분류 3종, KG 추출 (CPU, 순차)
- `labels.json`: KPF 라벨
- `result.json`: 마지막 실행 결과 (덮어씀)

## 기본 경로 (컨테이너)

| 용도 | 경로 |
|------|------|
| KG 번들 | `/models/artifacts/kg-extractor` |
| HF hub 캐시 | `/models/cache/hub` |

환경변수 `KG_MODEL_DIR`, `ARTICLELOCAL_HF_CACHE`로 덮어쓸 수 있다.
모델은 volume에서만 읽으며, 실행 중 다운로드하지 않는다 (`HF_HUB_OFFLINE`).

## 실행

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

성공 시 콘솔 예:

```text
1/2 KPF classification on CPU...
2/2 KG extraction on CPU...
PASSED: 9 nodes, 9 edges -> /work/result.json
```

## 이 서버에서 확인한 결과 (2026-09-10)

| 항목 | 값 |
|------|-----|
| 결과 | **PASSED** |
| 장치 | CPU |
| E2E (`docker run`마다, 로딩 포함) | 약 **12.7–13.3초** |
| 순수 추론만 (로딩 제외, 분해 측정) | 약 **4.9초** (KPF ~0.4 + KG ~4.5) |
| 로딩만 | 약 **7.3초** (KPF ~3.4 + KG ~3.9) |
| 분류 예 | 경제 / 취업_창업 / 지역일반 |
| KG | 9 nodes, 9 edges, validation PASS |

매 실행이 새 컨테이너라 E2E는 다음에도 비슷한 13초 전후가 정상이다.
워커 상주 시에는 이후 요청에서 로딩을 생략할 수 있다. 상주 가능 여부는 상위 README 참고.

`PASSED`는 추론·구조 검증 성공을 뜻하고 예측 정확도를 보장하지 않는다.
출력 JSON은 확인용 요약이며 DB 적재 스키마가 아니다.
KG 번들 일부 Relation은 비활성(부분 KG)이다.
