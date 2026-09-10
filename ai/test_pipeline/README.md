# CPU 추론 확인용 최소 예제

서버에 설치된 Python 환경과 모델로 **기사 1건 → 분류 + KG → 결과 JSON**이 출력되는지 확인합니다.
이 폴더만 Git에 올리면 됩니다. 상위 프로젝트 코드, 모델 가중치, API 키, DB 연결은 필요하지 않습니다.

## 파일
- `article.json`: 합성 기사 1건
- `pipeline.py`: 전처리, KPF 분류 3종, KG 추출 (CPU, 순차 실행)
- `labels.json`: KPF 라벨 이름 및 공식 출처
- `result.json`: 로컬에서 실제 실행한 요약 결과. 서버 실행 시 덮어씁니다.
- `.gitignore`: 캐시·가상환경 제외

## 서버 실행
설치해 둔 CPU 가상환경을 활성화하고 이 폴더에서 실행합니다.

```bash
python pipeline.py \
  --kg-dir /실제/경로/kg-extractor \
  --hf-cache /실제/경로/huggingface/hub
```

- `--kg-dir`: `config/pipeline.json`, `runtime/`, `models/`, `weights/`가 들어 있는 KG 번들 루트.
- `--hf-cache`: `models--KPF--KPF-bert-cls1` 같은 디렉터리가 있는 **hub 캐시 루트**. 기본 Hugging Face 캐시를 사용한다면 생략 가능합니다.
- 환경변수 `KG_MODEL_DIR`, `ARTICLELOCAL_HF_CACHE`로 경로를 지정해도 됩니다.
- KPF 모델/토크나이저 리비전은 코드에 고정되어 있으며, KG 베이스 리비전은 설치된 번들 설정을 따릅니다. 해당 스냅샷이 캐시에 있어야 합니다.
- 완전 오프라인으로 실행합니다. 캐시가 없으면 다운로드하지 않고 오류가 납니다.
- 개별 모델 폴더만 복사한 구조라면 이 코드의 Hugging Face 캐시 구조와 맞춰야 합니다.

검증된 의존성: Python 3.12, torch 2.6.0+cpu, transformers 4.51.3, huggingface-hub 0.30.2.
이 폴더에서는 패키지 설치나 모델 다운로드를 수행하지 않습니다.

성공 시 콘솔:
```text
1/2 KPF classification on CPU...
2/2 KG extraction on CPU...
PASSED: 9 nodes, 9 edges -> .../result.json
```

결과에는 기사, 분류 점수, KG 노드·연결, 검증 상태, 처리 시간이 들어갑니다.
원본 KG의 긴 근거·추적 정보는 생략한 출력 확인용 요약이며 DB 적재 스키마는 아닙니다.
`PASSED`는 추론·구조 검증 성공을 의미하고 예측 정확도를 보장하지 않습니다.
KG 번들의 일부 Relation 추출은 비활성화 상태입니다.
