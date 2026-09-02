# Figma 구현 핸드오프

이 디렉터리는 별빛 뉴스 Figma 파일을 실제 웹 목업으로 옮기기 위한 영구 자료입니다.

## 기준

- Figma file key: `N9IgiAcOTCRQQ1yigy4YXQ`
- 기준 viewport: 1440 × 900
- 실제 콘텐츠와 그래프 데이터의 유일한 기준: `data/mock/mock_dataset.json`
- Figma의 키워드, 기사, 고정 엣지 좌표는 시각 예시이며 런타임 데이터로 사용하지 않습니다.

## 구성

- `assets/`: Figma에서 직접 내려받은 재사용 SVG/PNG
- `screenshots/`: 최종 화면과 모션 pre/post 기준 이미지 26장
- `specs/frames.json`: 구현 화면, 상태, 데이터 연결점
- `specs/assets.json`: 에셋 출처, 용도, 해시
- `specs/tokens.css`: 구현용 의미 기반 디자인 토큰
- `specs/style-inventory.json`: Figma에서 검출한 전체 raw 스타일 값
- `specs/motion.json`: 웹에서 다시 구현할 모션 계약
- `specs/implementation-contract.md`: 그래프와 상호작용 구현 경계

Figma MCP가 반환한 임시 URL은 저장하지 않았습니다. 모든 런타임 에셋은 로컬 파일을 사용합니다.

## 글꼴

현재 최종 Figma 화면은 Noto Sans KR와 Noto Serif KR를 사용합니다. 루트의 전남교육바른체 Light 파일은 사용자가 제공한 후보 글꼴이지만 현재 Figma 기준 글꼴을 자동으로 대체하지 않습니다. 적용 여부는 구현 중 별도로 결정합니다.
