# 13번 v3 fresh-init training harness

표준 진입점은 프로젝트 루트에서 `conda run -n model-test-py312 python -m training.scripts.v3_train`이다. 인자를 생략하면 `validate-data`만 실행하며 모델이나 optimizer를 만들지 않는다. `--help`는 실제 모드를 표시한다.

```text
python -m training.scripts.v3_train validate-data
python -m training.scripts.v3_train compile --article-id GNEWS-cd62da87b3b7f539bf205f9df7db8ff1
python -m training.scripts.v3_train smoke --article-id GNEWS-cd62da87b3b7f539bf205f9df7db8ff1 --output-manifest docs/v3-pretraining/checkpoint-reload-manifest.json
python -m training.scripts.v3_train verify-checkpoint --checkpoint /path/to/smoke.pt
```

`validate-data`는 기존 source/split 해시와 train manifest를 확인한다. `compile`은 지정된 검증 train Gold의 exact span·pair target과 frozen source cache key만 만든다. `smoke`는 지정 기사 **1개**에서 pinned pretrained KF-DeBERTa를 frozen+eval/no_grad로 한 번씩 호출하고, 19개 task의 20개 loss 채널을 결합해 optimizer **1 step**만 실행한다. 마지막 accumulation group이 설정된 2기사보다 작아도 1 step으로 처리한다. `verify-checkpoint`는 별도 프로세스에서 고정 backbone을 다시 열고 fresh core에 strict load한 후 동일 train 입력의 eval loss/Primary scalar/final Event ID/target 서명을 비교한다. 이 단계의 `tiny-fit`, `main-train`, `evaluate`, `export-diagnostic`은 optimizer 생성 전에 명시적으로 거부한다. 실제 dev/test 평가, 본학습 또는 export는 아직 실행 경로가 아니다.

`training/configs/v3-harness-engineering-v1.json`은 19개 task의 learning rate와 20개 loss 가중치를 모두 명시한다. `entity_typing_union`은 `entity_mention`의 추가 Gold supervision 채널이다. 현재 가중치 1.0, task LR `1e-4`, shared LR `5e-5`, AdamW weight decay 0, pair negative/chunk 32, Primary pair 128, grad clip 1.0, accumulation 2기사는 **engineering smoke default**이며 dev/test로 조정하지 않았다. `curriculum_stage=ALL_19_HEADS_ENGINEERING_SMOKE`, `input_schedule=GOLD_TEACHER_FORCED_ENGINEERING`, `checkpoint_save_policy=SMOKE_ALWAYS_SAVE_NO_MODEL_SELECTION`이다. 각 adapter의 pair 평균을 먼저 계산하고, 활성 article의 task별 평균을 가중 합산한다. masked article은 그 task의 평균 분모에 들어가지 않는다. 같은 기사 안의 padding/window 반복을 새 positive로 세지 않는다.

Optimizer는 19 task owner와 5 shared owner의 이름/shape/parameter identity를 검사해 281개 trainable tensor, 총 10,211,761 parameter를 정확히 한 번씩 소유한다. Frozen backbone의 198 parameter tensor는 optimizer 밖이다. 단일 backbone의 L8/L10/L12 selective capture와 공유 DCE, direct gather, Event/Time member lease, final cluster의 RELATION/PRIMARY 마지막 소비 후 release를 유지한다. `source_cache_key`는 backbone model/revision/weight SHA, tokenizer SHA, layer/dtype, layout/window digest, source SHA를 포함한다. DCE 또는 trainable adapter 출력의 영구 캐시는 없다.

Checkpoint format은 `v3-fresh-train-checkpoint-v1`이다. task model state와 optimizer, scheduler/scaler 없음 계약, RNG(Python/NumPy/torch/CUDA), sampler cursor, step 수, run/seed/config, architecture, label mapping, producer code hash, frozen backbone/tokenizer identity, train Gold/split exposure snapshot, task registry, parameter manifest를 담는다. Backbone weight는 포함하지 않는다. `torch.load(weights_only=True)` 후 exact field/config/run/source/label/producer/parameter·optimizer ownership을 검사하며 `strict=True`로 model state를 읽는다. 부분·구버전·다른 run/config/Gold snapshot은 실패한다. Smoke checkpoint는 Git에서 제외되는 `training/results/v3-pretraining-step13-smoke/smoke.pt`에 로컬 저장되며 본학습 warm-start 자격이 없다. manifest는 `checkpoint-reload-manifest.json`, `training-run-exposure-manifest.json`, `training-parameter-manifest.json`에 기록했다.

최종 재현 검증은 검증 train Gold 1기사 `GNEWS-cd62da87b3b7f539bf205f9df7db8ff1`로 수행했다. 20 loss 채널 finite, 24 owner gradient·271개 parameter tensor 실제 변경, backbone parameter SHA 불변, 별도 프로세스 reload의 20 loss·15 Primary 출력·final Event IDs·exact source/pair/Primary target SHA parity가 통과했다. 또 다른 검증 train 기사에서 Time normalization masked 상태의 불완전 accumulation step을 검사하고, 검증 train 2기사의 full accumulation을 1 step으로 확인했다. PUBLIC 회귀 fixture는 checkpoint 전후 동일 결과를 확인했다. 구현 수정 과정에서 독립 fresh-init pretrained smoke를 총 5회 재실행했고, 각각 1 step으로 종료했다. 성능 평가나 학습된 모델 품질 승인은 아니다.

현재 Gold intake의 dev `136.json` Time interval granularity 오류는 그대로 남아 있다. 기존 split과 원본 Gold는 수정하지 않았다. `metric_policy.py`는 향후 head-conditional, predicted-cascade, selected-PUBLIC metric lane을 분리하고 test split 선택을 거부하는 순수 API만 제공한다. 이번 단계에서 실제 dev/test metric이나 early stopping 선택을 실행하지 않았다.
