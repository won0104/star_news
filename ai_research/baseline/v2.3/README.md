# ArticleLocal-KG v2.3 baseline (코드 열람용)

v2.3 릴리스의 모델·런타임 코드 사본입니다.
**학습된 weight(`weights/*.pt`, 약 83MB)는 포함하지 않아 이 디렉터리만으로는 실행되지 않습니다.**
실행이 필요하면 Hugging Face에서 받으세요 —
https://huggingface.co/sysy9292/kf-deberta-base-kg-extractor

이 코드에 대응하는 체크포인트는 `checkpoint_manifest.json`의 SHA로 확인할 수 있습니다.

`environment_manifest.json`과 `model_manifest.json`의 `"published": false`는
freeze 시점 상태를 기록한 값입니다. v2.3은 이후 실제로 배포되었으며,
배포 기록은 `ai_research/docs/95-release-v23/release-v23/publish-summary.md`에 있습니다.
