# 별빛 뉴스 웹 목업

Figma 핸드오프와 `data/mock/mock_dataset.json`을 바탕으로 만드는 브라우저 목업입니다.
런타임 의존성 없이 HTML, CSS, JavaScript ES Modules로 구성합니다.

## 실행

```bash
npm run serve
```

브라우저에서 `http://127.0.0.1:4173`을 엽니다. 개발 서버는 History API 경로를
`index.html`로 되돌리는 SPA fallback을 포함하므로 하위 화면 주소도 직접 열 수 있습니다.

## 검사

```bash
npm run check
npm test
```

## 구조

```text
index.html                       앱 진입점
src/app.js                      데이터·셸·라우터 조립
src/router.js                   History API 라우팅
src/components/app-shell.js     공통 사이드바·헤더·프로필 메뉴
src/data/repository.js          통합 목업 데이터 로드·뷰 모델 변환
src/pages/page-registry.js      경로별 화면 선택
src/styles/                     공통 셸·그래프·설정 화면 스타일
scripts/serve_mockup.py         SPA fallback 로컬 서버
tests/                          라우팅·데이터 변환 단위 테스트
```

화면 콘텐츠의 유일한 기준은 `data/mock/mock_dataset.json`입니다. Figma 프레임의
예시 키워드·기사·고정 좌표는 런타임 데이터로 사용하지 않습니다.

## 구현 범위

- 홈·분야별 탐색·검색에서 데이터 가중치에 따른 크기의 별을 선택하고 탐색을 시작합니다.
- SVG 탐색 그래프에서 가중치별 거리로 관계를 보고 경로를 되짚으며, 우측 고정 기사 패널의 내용을 노드별로 교체합니다.
- 나의 기록 군집을 필터로 사용하고, 최신순 읽기 기록과 리포트를 확인합니다.
- 전체 개인 기록 지도는 pan·zoom과 키보드 방향키 탐색을 지원합니다.
- 프로필 메뉴와 계정·관심 없음·화면 설정은 저장 전 검증과 상태 반영을 포함합니다.

웹 목업은 1024px 이상 데스크톱 화면을 기준으로 보정했습니다. 모션 감소 설정과
운영체제의 `prefers-reduced-motion`을 존중하며, 주요 그래프 노드는 키보드로도
탐색할 수 있습니다.
