# v3.1 후보 번들 생성

`scripts.finalize_v31_project_release`는 기존 v3.0 생성기의 Git HEAD 복사, 파일 SHA,
checkpoint·D2/E1·source policy 검증을 재사용한다. v3.1 D2/E1은
`training/configs/v3.1-runtime-participant-d2.json`과
`training/configs/v3.1-runtime-d2-e1.json`에서 가져온다. 현재 D2의
`PARTICIPANT_FINE=-0.25`는 미선정 임시값이고 `TRIGGER_FINE`과 기존 EntityIdentityHead의
`ENTITY_COREFERENCE` margin도 미선정이다. local Participant/Trigger fine head와
Entity identity 재학습, dev calibration, E1 latency 재검증이
기록되기 전에는 생성기가 중단된다.

현재 master의 V23 학습·서빙 경로를 수정한다. 별도 v3.1 model mode나 병렬 head는
없다. Trigger와 Entity의 score producer 및 feature 계약은
`docs/v3-pretraining/v31-trigger-entity-head-contract.md`에 기록한다.

## 다음 학습 전 확인 및 별도 기술 부채

- V23 학습 경로의 in-window `participant.span_score` 양성·reviewed negative 구분 손실은 `participant_decision`으로 최종 `losses["participant"]`에 포함된다. `tests/test_v3_v23_loss_reachability.py`가 해당 fine score의 gradient 도달을 검증한다.
- Participant cross-window 정책: 같은 문장 내 window 경계를 넘는 Participant는 지원 대상이고, 문장 간 Participant는 지원하지 않는다. 현재 V23 proposer의 실제 경계 처리 범위는 별도 구현 감사 대상으로 남긴다. 이번 변경에서 경로를 수정하지 않는다.
- exact feature cache의 512-row LRU에서 eviction 후 재계산은 성능 tuning 사안이다. 측정된 병목이 확인될 때만 cache 크기나 보존 정책을 조정한다.

변경 코드를 커밋해 tracked working tree를 깨끗하게 만든 뒤 프로젝트 루트에서 실행한다.
생성기는 작업 파일 대신 **Git HEAD**를 읽고, 기존 출력 디렉터리를 덮어쓰지 않는다.

```bash
conda run --no-capture-output -n model-test-py312 \
  python -m scripts.finalize_v31_project_release \
  --output release/kf-deberta-base-kg-extractor-v3.1-candidate
```

동일한 commit으로 다시 만들거나 후속 commit을 시험할 때는 새 `--output` 경로를 준다.
새 checkpoint가 선택되면 `project_release.py`의 checkpoint SHA 계약과 v3.1 D2/E1의
checkpoint binding도 함께 갱신해야 한다. 생성기는 학습과 calibration을 수행하지 않는다.

```bash
conda run --no-capture-output -n model-test-py312 \
  python release/kf-deberta-base-kg-extractor-v3.1-candidate/verify_bundle.py \
  --check-imports
```

`release-manifest.json`의 `release_version`은 `3.1-project-candidate-d2-e1`이고,
`source_git_commit`과 `files_sha256`이 코드·정책·템플릿을 고정한다. PUBLIC
projection version은 번들 안의 runtime 및 schema와 검증 시 일치해야 한다.
후보 번들의 validation 상태는 v3.0 base에서 승계되며 성능 승인으로 해석하지 않는다.

## Gold100 P6 진단용 후보

405번 기사 PUBLIC 경로를 확인할 때는 Gold100 미니 리허설의 P6 selected 체크포인트를
별도 후보로 묶는다. P6 dev15 source calibration과 predicted Entity pair margin
수집 결과를 사용한다. Entity margin의 명시적 KEEP 지원은 9쌍이고 complete-link
오류 검증은 없으므로 `service_ready=false`를 유지한다. E1 cap은 사용자 요청대로
고정하며 재검증됐다고 표시하지 않는다. 기존 v3.0 release와 1K main lineage는
변경하지 않는다.

```bash
conda run --no-capture-output -n model-test-py312 \
  python -m scripts.finalize_v31_project_release --mini-rehearsal \
  --output release/kf-deberta-base-kg-extractor-v3.1-gold100-mini-candidate-v3
```

이 진단용 후보는 현재 작업 트리의 포함 파일을 복사하며
`source_tree_mode=WORKING_TREE_SNAPSHOT`과 `source_snapshot_sha256`으로 고정한다.
`source_git_commit`은 코드 바이트의 출처로 해석하지 않는다. 실제 파일 SHA는
`files_sha256`에 있다. 번들은 `verify_bundle.py --check-imports`와 명시적
backbone snapshot을 사용한 smoke로 검사한다.
