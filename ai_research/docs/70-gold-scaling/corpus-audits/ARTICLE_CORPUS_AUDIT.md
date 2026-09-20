# ARTICLE CORPUS AUDIT

이 문서는 저장소의 GNews API raw 응답에 있는 `articles` row만 전수 스캔하여 관측된 구조와 검토 후보를 기록한다. 모든 반복 텍스트와 의심 콘텐츠는 **후보**이며 KEEP/REMOVE/RECOVER/REJECT 정책이 아니다.

## 1. Corpus Overview

- 스캔한 기사형 raw 파일: **1,197개** (기사 0개 응답 포함)
- article record: **5,316건**; source **440개**; URL domain **416개**
- GNews 보관 폴더 물리 파일 총 1,213개 중 API raw JSON 1,197개. 파생물·manifest·summary·README 등 16개는 기사 통계에서 제외했다.
- 파서 종류별 record: gnews_fullversion 3,987건, gnews_legacy 1,329건
- 기사형 raw 파일 종류별: gnews_fullversion 1,062개, gnews_legacy 135개.
- 반복 후보 고유 anchor: 줄 317개, 인접 블록 218개. 범위별 행으로 확장하면 총 1,178개다.
- API 오류 응답 원본: 2개 파일; article 0개 파일: 65개; 파싱 실패: 0개 파일.
- 제외 파일 확장자 분포: .jsonl 9개, .json 6개, .md 1개.
- `content` 길이는 GNews 원문 Unicode 문자 수이며 HTML 제거, 줄 정리, 중복 제거 등 전처리를 적용하지 않았다. source는 GNews `source.name`; category는 API 요청 경로 또는 기존 manifest의 `params.category`에서 읽었다.
- GNews `raw/` 응답만 원본으로 계산했다. `selected_articles.jsonl`, `normalized_articles.jsonl`, manifest, summary, Gold, processed 및 평가용 GNews 심볼릭 링크는 중복 수집 대상으로 보지 않았다.

## 2. Source / Domain Distribution

### Source별 전체 분포

| 항목 | article 수 | 비율 |
|---|---:|---:|
| v.daum.net | 370 | 6.96% |
| 연합뉴스 | 346 | 6.51% |
| 한겨레 | 340 | 6.40% |
| 경향신문 | 283 | 5.32% |
| 매일경제 | 264 | 4.97% |
| 지디넷코리아 | 245 | 4.61% |
| KBS 뉴스 | 241 | 4.53% |
| 한국경제 | 189 | 3.56% |
| tokenpost.kr | 121 | 2.28% |
| 문화일보 | 107 | 2.01% |
| 아시아경제 | 89 | 1.67% |
| YTN | 84 | 1.58% |
| 연합인포맥스 | 80 | 1.50% |
| 네이트 | 74 | 1.39% |
| 파이낸셜뉴스 | 70 | 1.32% |
| 뉴스핌 | 68 | 1.28% |
| starnewskorea.com | 67 | 1.26% |
| 스포츠경향 | 64 | 1.20% |
| 블록미디어 | 64 | 1.20% |
| 디지털투데이 | 63 | 1.19% |
| MBC 뉴스 | 60 | 1.13% |
| 스타뉴스 | 58 | 1.09% |
| 일간스포츠 | 55 | 1.03% |
| 글로벌이코노믹 | 50 | 0.94% |
| 한국일보 | 41 | 0.77% |
| 세계일보 | 40 | 0.75% |
| 코메디닷컴 | 40 | 0.75% |
| 연합뉴스 한민족센터 | 38 | 0.71% |
| 코인리더스 | 37 | 0.70% |
| 스포츠서울 | 35 | 0.66% |
| 머니투데이 | 35 | 0.66% |
| 헬스조선 | 34 | 0.64% |
| AI타임스 | 29 | 0.55% |
| OSEN | 28 | 0.53% |
| edaily.co.kr | 28 | 0.53% |
| 동아사이언스 | 26 | 0.49% |
| 메디컬투데이 | 26 | 0.49% |
| 스포츠동아 | 26 | 0.49% |
| 이데일리 | 24 | 0.45% |
| 전자신문 | 22 | 0.41% |
| segye.com | 21 | 0.40% |
| 마이데일리 | 20 | 0.38% |
| sportsseoul.com | 20 | 0.38% |
| 뉴시스 | 18 | 0.34% |
| 주간조선 | 17 | 0.32% |
| SBS 뉴스 | 17 | 0.32% |
| 뉴데일리 | 16 | 0.30% |
| 경기일보 | 16 | 0.30% |
| news.sbs.co.kr | 16 | 0.30% |
| 골프한국 | 16 | 0.30% |
| 히트뉴스 | 16 | 0.30% |
| 서울경제 | 15 | 0.28% |
| 서울신문 | 15 | 0.28% |
| 헤럴드경제 | 15 | 0.28% |
| 데일리안 | 14 | 0.26% |
| 아주경제 | 14 | 0.26% |
| 이투데이 | 13 | 0.24% |
| 헬스코리아뉴스 | 13 | 0.24% |
| 후생신보 | 13 | 0.24% |
| 조선일보 | 13 | 0.24% |
| 중앙일보 | 12 | 0.23% |
| 하이닥 | 12 | 0.23% |
| 메디칼업저버 | 12 | 0.23% |
| 아이뉴스24 | 11 | 0.21% |
| 에너지경제신문 | 11 | 0.21% |
| Hyundai Motor Group | 11 | 0.21% |
| 채널A | 10 | 0.19% |
| gukjenews.com | 10 | 0.19% |
| sports.donga.com | 10 | 0.19% |
| 헬로디디 | 10 | 0.19% |
| 메디칼트리뷴 | 10 | 0.19% |
| SPOTV NEWS | 10 | 0.19% |
| 네이트 스포츠 | 10 | 0.19% |
| osen.co.kr | 10 | 0.19% |
| VOA 한국어 홈페이지 | 9 | 0.17% |
| 톱스타뉴스 | 9 | 0.17% |
| 코리아헬스로그 | 9 | 0.17% |
| 메드월드뉴스 | 9 | 0.17% |
| 데일리메디 | 9 | 0.17% |
| 의학신문 | 9 | 0.17% |
| hankyung.com | 9 | 0.17% |
| fnnews.com | 9 | 0.17% |
| 매일일보 | 8 | 0.15% |
| BBC | 8 | 0.15% |
| IT조선 | 8 | 0.15% |
| 청년의사 | 8 | 0.15% |
| 메디포뉴스 | 8 | 0.15% |
| bntnews.co.kr | 8 | 0.15% |
| sportschosun.com | 8 | 0.15% |
| 매일신문 | 7 | 0.13% |
| 대한민국 정책브리핑 | 7 | 0.13% |
| 머니S | 7 | 0.13% |
| 한겨레21 | 7 | 0.13% |
| 미디어데일 | 7 | 0.13% |
| 디지털데일리 | 7 | 0.13% |
| GameGPU | 6 | 0.11% |
| 더구루 | 6 | 0.11% |
| TV조선뉴스 | 6 | 0.11% |
| 국제신문 | 6 | 0.11% |
| 위키트리 | 6 | 0.11% |
| 한국강사신문 | 6 | 0.11% |
| 미디어파인 | 6 | 0.11% |
| 해사신문 | 6 | 0.11% |
| 헬스경향 | 6 | 0.11% |
| 뉴스티앤티 | 6 | 0.11% |
| 현대건강신문 | 6 | 0.11% |
| 의료&복지뉴스 | 6 | 0.11% |
| 영남일보 | 5 | 0.09% |
| 천지일보 | 5 | 0.09% |
| 인벤 | 5 | 0.09% |
| 대전일보 | 5 | 0.09% |
| 조세일보 | 5 | 0.09% |
| 주간경향 | 5 | 0.09% |
| 미디어오늘 | 5 | 0.09% |
| ER 이코노믹리뷰 | 5 | 0.09% |
| 텐아시아 | 5 | 0.09% |
| 서울파이낸스 | 5 | 0.09% |
| 의약뉴스 | 5 | 0.09% |
| 블로터 | 5 | 0.09% |
| 스포츠니어스 | 5 | 0.09% |
| 프레시안 | 5 | 0.09% |
| 데이터솜 | 5 | 0.09% |
| 스포츠조선 | 5 | 0.09% |
| 동아일보 | 5 | 0.09% |
| 농민신문 | 5 | 0.09% |
| 비즈워치 | 5 | 0.09% |
| MTN 머니투데이방송 | 5 | 0.09% |
| 약업신문 | 5 | 0.09% |
| 바이오스펙테이터 | 5 | 0.09% |
| 서울뉴스통신 | 5 | 0.09% |
| SK텔레콤 뉴스룸 | 5 | 0.09% |
| dt.co.kr | 5 | 0.09% |
| 딜사이트 | 5 | 0.09% |
| 뉴데일리 경제 | 5 | 0.09% |
| eMD Medical News | 5 | 0.09% |
| hidomin.com | 4 | 0.08% |
| 시사저널e | 4 | 0.08% |
| 보건신문 | 4 | 0.08% |
| 매경헬스 | 4 | 0.08% |
| 한국NGO신문 | 4 | 0.08% |
| 한국의약통신 | 4 | 0.08% |
| 제주의소리 | 4 | 0.08% |
| 뉴스와 | 4 | 0.08% |
| 이코노미톡뉴스 | 4 | 0.08% |
| c3korea.net | 4 | 0.08% |
| 케이에스피뉴스 | 4 | 0.08% |
| 중소기업신문 | 4 | 0.08% |
| 병원신문 | 4 | 0.08% |
| ZUM 뉴스 | 4 | 0.08% |
| hani.co.kr | 4 | 0.08% |
| 서울En | 4 | 0.08% |
| 한국AI부동산신문 | 4 | 0.08% |
| 의사신문 | 4 | 0.08% |
| 게임뷰 | 4 | 0.08% |
| harpersbazaar.co.kr | 4 | 0.08% |
| 에너지경제신문 모바일 | 4 | 0.08% |
| 뉴스톱 | 4 | 0.08% |
| twig24.com | 4 | 0.08% |
| yna.co.kr | 4 | 0.08% |
| 한스경제 | 4 | 0.08% |
| 더바이오 | 4 | 0.08% |
| zdnet.co.kr | 4 | 0.08% |
| 슬로우뉴스 | 4 | 0.08% |
| 대구MBC | 3 | 0.06% |
| 네이버 프리미엄콘텐츠 | 3 | 0.06% |
| OhmyNews | 3 | 0.06% |
| xportsnews.com | 3 | 0.06% |
| 중부일보 | 3 | 0.06% |
| RadioKorea | 3 | 0.06% |
| Laodong.vn | 3 | 0.06% |
| 뉴스타파 | 3 | 0.06% |
| 약품신문 | 3 | 0.06% |
| 팜뉴스 | 3 | 0.06% |
| 이코노미사이언스 | 3 | 0.06% |
| 내외경제TV | 3 | 0.06% |
| 유스연합 | 3 | 0.06% |
| 뉴스데일리 | 3 | 0.06% |
| AI넷 | 3 | 0.06% |
| CNET Korea | 3 | 0.06% |
| 메디칼타임즈 | 3 | 0.06% |
| 인공지능신문 | 3 | 0.06% |
| 부산일보 | 3 | 0.06% |
| 민주노총 | 3 | 0.06% |
| 마음건강 길 | 3 | 0.06% |
| 헬스오 | 3 | 0.06% |
| 초이스경제 | 3 | 0.06% |
| the-real.kr | 3 | 0.06% |
| spotvnews.co.kr | 3 | 0.06% |
| 스포츠한국 | 3 | 0.06% |
| 아시아투데이 | 3 | 0.06% |
| Vietnam.vn | 3 | 0.06% |
| 전라일보 | 2 | 0.04% |
| IGN Korea | 2 | 0.04% |
| 더게이트 | 2 | 0.04% |
| mhnse.com | 2 | 0.04% |
| 뉴스탭 | 2 | 0.04% |
| 한국아이닷컴 | 2 | 0.04% |
| 신아일보 | 2 | 0.04% |
| 진주뉴스 | 2 | 0.04% |
| GQ Korea | 2 | 0.04% |
| 오토트리뷴 | 2 | 0.04% |
| 돼지와사람 | 2 | 0.04% |
| 나우뉴스 | 2 | 0.04% |
| 누리일보 | 2 | 0.04% |
| 바이라인네트워크 | 2 | 0.04% |
| 부산경남대표방송 KNN | 2 | 0.04% |
| 베타뉴스 | 2 | 0.04% |
| econovill.com | 2 | 0.04% |
| isplus.com | 2 | 0.04% |
| 인베스트조선 | 2 | 0.04% |
| 전자부품 전문 미디어 디일렉 | 2 | 0.04% |
| 컨슈머타임스 | 2 | 0.04% |
| 디지털타임스 | 2 | 0.04% |
| 에너지타임즈 | 2 | 0.04% |
| 한국세정신문 | 2 | 0.04% |
| Автомобильный портал 32CARS.RU | 2 | 0.04% |
| kakaocorp.com | 2 | 0.04% |
| 전북일보 인터넷신문 | 2 | 0.04% |
| mlbkor.com | 2 | 0.04% |
| 교수신문 | 2 | 0.04% |
| 서울경제TV | 2 | 0.04% |
| 미디어스 | 2 | 0.04% |
| knn.co.kr | 2 | 0.04% |
| 시애틀코리안데일리 | 2 | 0.04% |
| 에너지데일리 | 2 | 0.04% |
| 오마이뉴스 | 2 | 0.04% |
| 비욘드포스트 | 2 | 0.04% |
| 일요시사 | 2 | 0.04% |
| tvreport.co.kr | 2 | 0.04% |
| Milano Cortina 2026 | 2 | 0.04% |
| 뉴스컬처 | 2 | 0.04% |
| 월간 믹싱 | 2 | 0.04% |
| 메디코파마 | 2 | 0.04% |
| 전국뉴스 | 2 | 0.04% |
| 뉴스웨이 | 2 | 0.04% |
| MEDI:GATE NEWS | 2 | 0.04% |
| topstarnews.net | 2 | 0.04% |
| khan.co.kr | 2 | 0.04% |
| news.kbs.co.kr | 2 | 0.04% |
| 시사저널 | 2 | 0.04% |
| 핀포인트뉴스 | 2 | 0.04% |
| 프라임경제 | 2 | 0.04% |
| 인더스트리뉴스 | 2 | 0.04% |
| 강원도민일보 | 2 | 0.04% |
| 전기신문 | 2 | 0.04% |
| 덴 매거진 | 2 | 0.04% |
| 시사일보 | 2 | 0.04% |
| 메디소비자뉴스 | 2 | 0.04% |
| supple.kr | 2 | 0.04% |
| 가톨릭신문 | 2 | 0.04% |
| 디지털포커스 | 2 | 0.04% |
| 데일리대구경북뉴스 | 2 | 0.04% |
| kyongbuk.co.kr | 1 | 0.02% |
| 경남도민일보 | 1 | 0.02% |
| 경북매일 | 1 | 0.02% |
| 뉴스후플러스 | 1 | 0.02% |
| 코나스넷 | 1 | 0.02% |
| 비건뉴스 | 1 | 0.02% |
| M이코노미뉴스 | 1 | 0.02% |
| 금강일보 | 1 | 0.02% |
| OMATE 시니어 | 1 | 0.02% |
| 뉴스에듀신문 | 1 | 0.02% |
| sisaworld.kr | 1 | 0.02% |
| 디지털애셋 | 1 | 0.02% |
| DongA Science | 1 | 0.02% |
| 뉴스인 | 1 | 0.02% |
| 뉴스웍스 | 1 | 0.02% |
| 파이낸스투데이 | 1 | 0.02% |
| ABC뉴스 | 1 | 0.02% |
| 참여연대 | 1 | 0.02% |
| 미디어제주 | 1 | 0.02% |
| ibabynews.com | 1 | 0.02% |
| 위클리서울 | 1 | 0.02% |
| 톱클래스 | 1 | 0.02% |
| 한국경제TV | 1 | 0.02% |
| 파이낸셜포스트 | 1 | 0.02% |
| 소년한국일보 | 1 | 0.02% |
| 드론저널 | 1 | 0.02% |
| 울산종합일보 | 1 | 0.02% |
| 리드경제 | 1 | 0.02% |
| 공감신문 | 1 | 0.02% |
| 동방일보 | 1 | 0.02% |
| 서울특별시 | 1 | 0.02% |
| 간호사신문 | 1 | 0.02% |
| 애드뉴스인천 | 1 | 0.02% |
| 엔지니어링데일리 | 1 | 0.02% |
| 씨네21 | 1 | 0.02% |
| 시사뉴스 | 1 | 0.02% |
| 미디어생활 | 1 | 0.02% |
| 조이뉴스24 | 1 | 0.02% |
| 미디어워치 | 1 | 0.02% |
| 울산일보 | 1 | 0.02% |
| 조선일보 LA | 1 | 0.02% |
| MIT 테크놀로지 리뷰 | 1 | 0.02% |
| 팍스경제TV | 1 | 0.02% |
| 치의신보 | 1 | 0.02% |
| 식품산업경제뉴스 | 1 | 0.02% |
| vegannews.co.kr | 1 | 0.02% |
| 데일리머니 | 1 | 0.02% |
| 더스쿠프 | 1 | 0.02% |
| 이코노미스트 | 1 | 0.02% |
| 쉬핑뉴스넷 | 1 | 0.02% |
| 테크M | 1 | 0.02% |
| 양산신문 | 1 | 0.02% |
| 밴쿠버 조선일보 | 1 | 0.02% |
| 덴탈아리랑 | 1 | 0.02% |
| car.withnews.kr | 1 | 0.02% |
| 한국생활체육뉴스 | 1 | 0.02% |
| 대학신문 | 1 | 0.02% |
| 삼성물산 뉴스룸 | 1 | 0.02% |
| 뉴스더보이스헬스케어 | 1 | 0.02% |
| 쿠키뉴스 | 1 | 0.02% |
| 충청투데이 | 1 | 0.02% |
| 애틀랜타 중앙일보 | 1 | 0.02% |
| 경제정의실천시민연합 | 1 | 0.02% |
| 컨슈머타임스(Consumertimes) | 1 | 0.02% |
| 녹색경제신문 | 1 | 0.02% |
| 철강금속신문 | 1 | 0.02% |
| SpeedMe.ru | 1 | 0.02% |
| 정필 | 1 | 0.02% |
| TWIG24 | 1 | 0.02% |
| kairnews.com | 1 | 0.02% |
| 드림투데이 | 1 | 0.02% |
| 더인디고 | 1 | 0.02% |
| 프리진뉴스 | 1 | 0.02% |
| 고양신문 | 1 | 0.02% |
| mhns.co.kr | 1 | 0.02% |
| 아이보스 | 1 | 0.02% |
| 테크42 | 1 | 0.02% |
| 교통뉴스 | 1 | 0.02% |
| 파퓰러사이언스 | 1 | 0.02% |
| Mix Vale | 1 | 0.02% |
| 디일렉 | 1 | 0.02% |
| 노컷뉴스 | 1 | 0.02% |
| 데일리안 미디어 | 1 | 0.02% |
| 아웃소싱타임스 | 1 | 0.02% |
| sedaily.com | 1 | 0.02% |
| 뉴스1 | 1 | 0.02% |
| 브릿지경제 | 1 | 0.02% |
| 더팩트 | 1 | 0.02% |
| 바이크매거진 | 1 | 0.02% |
| abcn.kr | 1 | 0.02% |
| 충청일보 | 1 | 0.02% |
| 민주신문 | 1 | 0.02% |
| 성남시 시정소식지 비전성남 | 1 | 0.02% |
| dgmbc.com | 1 | 0.02% |
| koreancenter.or.kr | 1 | 0.02% |
| ELLE | 1 | 0.02% |
| 소셜타임스 | 1 | 0.02% |
| 뷰어스 | 1 | 0.02% |
| bundangnews.co.kr | 1 | 0.02% |
| 부천포커스 | 1 | 0.02% |
| 스포츠월드 | 1 | 0.02% |
| 코스모닝 | 1 | 0.02% |
| 코리아이글뉴스 | 1 | 0.02% |
| 전남일보 | 1 | 0.02% |
| 싱글리스트 | 1 | 0.02% |
| 위키리크스한국 | 1 | 0.02% |
| 금융경제플러스 | 1 | 0.02% |
| тарантас ньюс | 1 | 0.02% |
| Joseilbo.com | 1 | 0.02% |
| 조선일보 - 1등 디지털뉴스 | 1 | 0.02% |
| HeraldK.com | 1 | 0.02% |
| 라디오코리아 모바일 | 1 | 0.02% |
| fetv.co.kr | 1 | 0.02% |
| sidae.com | 1 | 0.02% |
| 한의신문 | 1 | 0.02% |
| 매일노동뉴스 | 1 | 0.02% |
| mt.co.kr | 1 | 0.02% |
| 캐나다 한국일보 | 1 | 0.02% |
| 웰페어뉴스 | 1 | 0.02% |
| 뉴스인스타 | 1 | 0.02% |
| 수원일보 | 1 | 0.02% |
| greened.kr | 1 | 0.02% |
| news.nate.com | 1 | 0.02% |
| munhwa.com | 1 | 0.02% |
| 중앙이코노미뉴스 | 1 | 0.02% |
| 디스패치 | 1 | 0.02% |
| 무등일보 | 1 | 0.02% |
| 오피니언뉴스 | 1 | 0.02% |
| nocutnews.co.kr | 1 | 0.02% |
| ytn.co.kr | 1 | 0.02% |
| 디지털포용뉴스 | 1 | 0.02% |
| 이뉴스투데이 | 1 | 0.02% |
| 강원일보 | 1 | 0.02% |
| 호주 톱뉴스 | 1 | 0.02% |
| 내외일보 | 1 | 0.02% |
| olympics.com | 1 | 0.02% |
| 뉴스버스 | 1 | 0.02% |
| 뉴스앤북 | 1 | 0.02% |
| TV리포트 | 1 | 0.02% |
| 브랜드경제신문 | 1 | 0.02% |
| kmjournal.net | 1 | 0.02% |
| 알파경제 | 1 | 0.02% |
| 빅데이터뉴스 | 1 | 0.02% |
| mydaily.co.kr | 1 | 0.02% |
| 디지틀조선일보 | 1 | 0.02% |
| insight.co.kr | 1 | 0.02% |
| 게임톡 | 1 | 0.02% |
| 이슈밸리 | 1 | 0.02% |
| 게임동아 | 1 | 0.02% |
| 전파신문 | 1 | 0.02% |
| 에이빙 | 1 | 0.02% |
| 시정일보 | 1 | 0.02% |
| 재외동포신문 | 1 | 0.02% |
| 스마트투데이 | 1 | 0.02% |
| OBS경인TV | 1 | 0.02% |
| 브랜드브리프 | 1 | 0.02% |
| SPI - 상업용 부동산 콘텐츠 & 데이터 애널리틱스 | 1 | 0.02% |
| 씬짜오베트남 | 1 | 0.02% |
| KBC광주방송 | 1 | 0.02% |
| 국악타임즈 | 1 | 0.02% |
| DailyNK | 1 | 0.02% |
| 아세안데일리 뉴스 | 1 | 0.02% |
| 경북정치신문 | 1 | 0.02% |
| 경북일보 | 1 | 0.02% |
| 성남일보 | 1 | 0.02% |
| 디스이즈게임 | 1 | 0.02% |
| 세상을 바꾸는 시민언론 민들레 | 1 | 0.02% |
| 오토헤럴드 | 1 | 0.02% |
| kids.donga.com | 1 | 0.02% |
| 연합투데이 | 1 | 0.02% |
| 비마이너 | 1 | 0.02% |
| monthly.chosun.com | 1 | 0.02% |
| 데일리팜 | 1 | 0.02% |
| 컨슈머치 | 1 | 0.02% |
| hankookilbo.com | 1 | 0.02% |
| ekn.kr | 1 | 0.02% |
| news.einfomax.co.kr | 1 | 0.02% |
| BRIC | 1 | 0.02% |
| 베이비뉴스 | 1 | 0.02% |
| digitaltoday.co.kr | 1 | 0.02% |
| biz.heraldcorp.com | 1 | 0.02% |
| Tarantas News | 1 | 0.02% |
| 얼리어답터뉴스 | 1 | 0.02% |
| mk.co.kr | 1 | 0.02% |
| 골프경제신문 | 1 | 0.02% |
| 보안뉴스 | 1 | 0.02% |
| incheonin.com | 1 | 0.02% |
| 지이코노미 | 1 | 0.02% |

### Domain별 전체 분포

| 항목 | article 수 | 비율 |
|---|---:|---:|
| v.daum.net | 370 | 6.96% |
| www.yna.co.kr | 350 | 6.58% |
| www.hani.co.kr | 344 | 6.47% |
| www.khan.co.kr | 285 | 5.36% |
| www.mk.co.kr | 265 | 4.98% |
| zdnet.co.kr | 249 | 4.68% |
| news.kbs.co.kr | 243 | 4.57% |
| www.hankyung.com | 198 | 3.72% |
| www.starnewskorea.com | 125 | 2.35% |
| www.tokenpost.kr | 121 | 2.28% |
| www.munhwa.com | 108 | 2.03% |
| www.ytn.co.kr | 82 | 1.54% |
| news.einfomax.co.kr | 81 | 1.52% |
| www.fnnews.com | 79 | 1.49% |
| www.newspim.com | 65 | 1.22% |
| sports.khan.co.kr | 64 | 1.20% |
| www.digitaltoday.co.kr | 64 | 1.20% |
| www.blockmedia.co.kr | 64 | 1.20% |
| www.segye.com | 61 | 1.15% |
| www.asiae.co.kr | 61 | 1.15% |
| imnews.imbc.com | 60 | 1.13% |
| isplus.com | 57 | 1.07% |
| www.sportsseoul.com | 55 | 1.03% |
| news.nate.com | 52 | 0.98% |
| www.edaily.co.kr | 52 | 0.98% |
| www.g-enews.com | 47 | 0.88% |
| www.hankookilbo.com | 42 | 0.79% |
| kormedi.com | 40 | 0.75% |
| www.koreancenter.or.kr | 39 | 0.73% |
| www.osen.co.kr | 38 | 0.71% |
| www.mt.co.kr | 36 | 0.68% |
| sports.donga.com | 36 | 0.68% |
| www.coinreaders.com | 34 | 0.64% |
| news.sbs.co.kr | 33 | 0.62% |
| www.aitimes.com | 29 | 0.55% |
| m.health.chosun.com | 27 | 0.51% |
| cm.asiae.co.kr | 26 | 0.49% |
| www.dongascience.com | 22 | 0.41% |
| sports.news.nate.com | 22 | 0.41% |
| www.mydaily.co.kr | 21 | 0.40% |
| health.chosun.com | 19 | 0.36% |
| weekly.chosun.com | 19 | 0.36% |
| www.etnews.com | 18 | 0.34% |
| mdtoday.co.kr | 17 | 0.32% |
| www.kyeonggi.com | 16 | 0.30% |
| golfhankook.hankooki.com | 16 | 0.30% |
| www.hitnews.co.kr | 16 | 0.30% |
| www.newdaily.co.kr | 15 | 0.28% |
| www.sedaily.com | 15 | 0.28% |
| mobile.newsis.com | 15 | 0.28% |
| www.ajunews.com | 14 | 0.26% |
| www.hkn24.com | 13 | 0.24% |
| www.sportschosun.com | 13 | 0.24% |
| www.whosaeng.com | 13 | 0.24% |
| www.spotvnews.co.kr | 13 | 0.24% |
| www.dailian.co.kr | 12 | 0.23% |
| www.joongang.co.kr | 12 | 0.23% |
| www.etoday.co.kr | 12 | 0.23% |
| www.seoul.co.kr | 12 | 0.23% |
| news.hidoc.co.kr | 12 | 0.23% |
| www.monews.co.kr | 12 | 0.23% |
| www.inews24.com | 11 | 0.21% |
| www.topstarnews.net | 11 | 0.21% |
| biz.heraldcorp.com | 11 | 0.21% |
| m.news.nate.com | 11 | 0.21% |
| www.hyundaimotorgroup.com | 11 | 0.21% |
| ichannela.com | 10 | 0.19% |
| www.gukjenews.com | 10 | 0.19% |
| www.hellodd.com | 10 | 0.19% |
| www.medical-tribune.co.kr | 10 | 0.19% |
| www.voakorea.com | 9 | 0.17% |
| m.ekn.kr | 9 | 0.17% |
| www.koreahealthlog.com | 9 | 0.17% |
| www.medworld.co.kr | 9 | 0.17% |
| www.dailymedi.com | 9 | 0.17% |
| www.bosa.co.kr | 9 | 0.17% |
| www.m-i.kr | 8 | 0.15% |
| www.bbc.com | 8 | 0.15% |
| it.chosun.com | 8 | 0.15% |
| www.docdocdoc.co.kr | 8 | 0.15% |
| www.medifonews.com | 8 | 0.15% |
| www.bntnews.co.kr | 8 | 0.15% |
| www.econovill.com | 7 | 0.13% |
| www.imaeil.com | 7 | 0.13% |
| www.korea.kr | 7 | 0.13% |
| www.dt.co.kr | 7 | 0.13% |
| www.moneys.co.kr | 7 | 0.13% |
| h21.hani.co.kr | 7 | 0.13% |
| www.mediadale.com | 7 | 0.13% |
| ko.gamegpu.com | 6 | 0.11% |
| news.tvchosun.com | 6 | 0.11% |
| www.kookje.co.kr | 6 | 0.11% |
| www.wikitree.co.kr | 6 | 0.11% |
| www.lecturernews.com | 6 | 0.11% |
| www.mediafine.co.kr | 6 | 0.11% |
| www.haesanews.com | 6 | 0.11% |
| www.k-health.com | 6 | 0.11% |
| www.newstnt.com | 6 | 0.11% |
| www.mdtoday.co.kr | 6 | 0.11% |
| biz.newdaily.co.kr | 6 | 0.11% |
| en.seoul.co.kr | 6 | 0.11% |
| www.mediwelfare.com | 6 | 0.11% |
| www.ddaily.co.kr | 6 | 0.11% |
| www.theguru.co.kr | 5 | 0.09% |
| www.yeongnam.com | 5 | 0.09% |
| www.newscj.com | 5 | 0.09% |
| www.inven.co.kr | 5 | 0.09% |
| www.daejonilbo.com | 5 | 0.09% |
| weekly.khan.co.kr | 5 | 0.09% |
| www.mediatoday.co.kr | 5 | 0.09% |
| www.ohmynews.com | 5 | 0.09% |
| www.ekn.kr | 5 | 0.09% |
| www.tenasia.co.kr | 5 | 0.09% |
| www.seoulfn.com | 5 | 0.09% |
| www.newsmp.com | 5 | 0.09% |
| www.bloter.net | 5 | 0.09% |
| www.sports-g.com | 5 | 0.09% |
| www.pressian.com | 5 | 0.09% |
| www.datasom.co.kr | 5 | 0.09% |
| mbiz.heraldcorp.com | 5 | 0.09% |
| www.donga.com | 5 | 0.09% |
| www.nongmin.com | 5 | 0.09% |
| news.bizwatch.co.kr | 5 | 0.09% |
| news.mtn.co.kr | 5 | 0.09% |
| www.biospectator.com | 5 | 0.09% |
| www.snakorea.com | 5 | 0.09% |
| news.sktelecom.com | 5 | 0.09% |
| dealsite.co.kr | 5 | 0.09% |
| m.dongascience.com | 5 | 0.09% |
| www.hnews.kr | 5 | 0.09% |
| www.kairnews.com | 5 | 0.09% |
| www.twig24.com | 5 | 0.09% |
| www.mdon.co.kr | 5 | 0.09% |
| dgmbc.com | 4 | 0.08% |
| www.hidomin.com | 4 | 0.08% |
| www.joseilbo.com | 4 | 0.08% |
| www.sisajournal-e.com | 4 | 0.08% |
| www.bokuennews.com | 4 | 0.08% |
| www.mkhealth.co.kr | 4 | 0.08% |
| www.ngonews.kr | 4 | 0.08% |
| www.kmpnews.co.kr | 4 | 0.08% |
| www.jejusori.net | 4 | 0.08% |
| www.news-wa.com | 4 | 0.08% |
| www.economytalk.kr | 4 | 0.08% |
| news.knn.co.kr | 4 | 0.08% |
| www.c3korea.net | 4 | 0.08% |
| www.kspnews.com | 4 | 0.08% |
| www.smedaily.co.kr | 4 | 0.08% |
| www.khanews.com | 4 | 0.08% |
| m.news.zum.com | 4 | 0.08% |
| www.doctorstimes.com | 4 | 0.08% |
| www.gamevu.co.kr | 4 | 0.08% |
| www.harpersbazaar.co.kr | 4 | 0.08% |
| www.newstopkorea.com | 4 | 0.08% |
| www.hansbiz.co.kr | 4 | 0.08% |
| m.etnews.com | 4 | 0.08% |
| www.thebionews.net | 4 | 0.08% |
| slownews.kr | 4 | 0.08% |
| contents.premium.naver.com | 3 | 0.06% |
| www.xportsnews.com | 3 | 0.06% |
| www.joongboo.com | 3 | 0.06% |
| m.newspim.com | 3 | 0.06% |
| www.radiokorea.com | 3 | 0.06% |
| ko.laodong.vn | 3 | 0.06% |
| www.yakpum.co.kr | 3 | 0.06% |
| www.pharmnews.com | 3 | 0.06% |
| www.e-science.co.kr | 3 | 0.06% |
| www.nbntv.co.kr | 3 | 0.06% |
| www.youthassembly.kr | 3 | 0.06% |
| m.yakup.com | 3 | 0.06% |
| www.newsdaily.kr | 3 | 0.06% |
| m.mdtoday.co.kr | 3 | 0.06% |
| www.ainet.link | 3 | 0.06% |
| www.cnet.co.kr | 3 | 0.06% |
| www.cstimes.com | 3 | 0.06% |
| www.medicaltimes.com | 3 | 0.06% |
| m.g-enews.com | 3 | 0.06% |
| www.aitimes.kr | 3 | 0.06% |
| nodong.org | 3 | 0.06% |
| www.mindgil.com | 3 | 0.06% |
| star.ytn.co.kr | 3 | 0.06% |
| healtho.co.kr | 3 | 0.06% |
| www.choicenews.co.kr | 3 | 0.06% |
| www.the-real.kr | 3 | 0.06% |
| sports.hankooki.com | 3 | 0.06% |
| tvreport.co.kr | 3 | 0.06% |
| www.olympics.com | 3 | 0.06% |
| m.coinreaders.com | 3 | 0.06% |
| www.asiatoday.co.kr | 3 | 0.06% |
| www.vietnam.vn | 3 | 0.06% |
| www.kyongbuk.co.kr | 2 | 0.04% |
| www.jeollailbo.com | 2 | 0.04% |
| kr.ign.com | 2 | 0.04% |
| ekn.kr | 2 | 0.04% |
| www.spochoo.com | 2 | 0.04% |
| www.vegannews.co.kr | 2 | 0.04% |
| core.asiae.co.kr | 2 | 0.04% |
| nwww.newsis.com | 2 | 0.04% |
| www.newstap.co.kr | 2 | 0.04% |
| www.hankooki.com | 2 | 0.04% |
| www.shinailbo.co.kr | 2 | 0.04% |
| www.jinjutv.com | 2 | 0.04% |
| www.gqkorea.co.kr | 2 | 0.04% |
| www.autotribune.co.kr | 2 | 0.04% |
| www.abcn.kr | 2 | 0.04% |
| www.pigpeople.net | 2 | 0.04% |
| m.joseilbo.com | 2 | 0.04% |
| www.ibabynews.com | 2 | 0.04% |
| nownews.seoul.co.kr | 2 | 0.04% |
| nuriilbo.com | 2 | 0.04% |
| newstapa.org | 2 | 0.04% |
| byline.network | 2 | 0.04% |
| www.betanews.net | 2 | 0.04% |
| dailian.co.kr | 2 | 0.04% |
| www.investchosun.com | 2 | 0.04% |
| www.thelec.kr | 2 | 0.04% |
| www.energytimes.kr | 2 | 0.04% |
| www.taxtimes.co.kr | 2 | 0.04% |
| www.greened.kr | 2 | 0.04% |
| www.32cars.ru | 2 | 0.04% |
| www.kakaocorp.com | 2 | 0.04% |
| www.busan.com | 2 | 0.04% |
| www.jjan.kr | 2 | 0.04% |
| www.mlbkor.com | 2 | 0.04% |
| www.kyosu.net | 2 | 0.04% |
| www.sentv.co.kr | 2 | 0.04% |
| www.nocutnews.co.kr | 2 | 0.04% |
| www.mediaus.co.kr | 2 | 0.04% |
| www.seattlekdaily.com | 2 | 0.04% |
| www.energydaily.co.kr | 2 | 0.04% |
| www.beyondpost.co.kr | 2 | 0.04% |
| www.ilyosisa.co.kr | 2 | 0.04% |
| tarantas.news | 2 | 0.04% |
| www.nc.press | 2 | 0.04% |
| mixing.co.kr | 2 | 0.04% |
| www.medicopharma.co.kr | 2 | 0.04% |
| www.jeonguknews.co.kr | 2 | 0.04% |
| www.newsway.co.kr | 2 | 0.04% |
| m.medigatenews.com | 2 | 0.04% |
| www.sisajournal.com | 2 | 0.04% |
| www.yakup.com | 2 | 0.04% |
| www.pinpointnews.co.kr | 2 | 0.04% |
| www.newsprime.co.kr | 2 | 0.04% |
| www.industrynews.co.kr | 2 | 0.04% |
| www.kado.net | 2 | 0.04% |
| www.electimes.com | 2 | 0.04% |
| www.theden.co.kr | 2 | 0.04% |
| www.koreasisailbo.com | 2 | 0.04% |
| www.medisobizanews.com | 2 | 0.04% |
| supple.kr | 2 | 0.04% |
| www.catholictimes.org | 2 | 0.04% |
| www.digitalfocus.news | 2 | 0.04% |
| www.dailydgnews.com | 2 | 0.04% |
| www.idomin.com | 1 | 0.02% |
| www.kbmaeil.com | 1 | 0.02% |
| www.newswhoplus.com | 1 | 0.02% |
| www.konas.net | 1 | 0.02% |
| www.m-economynews.com | 1 | 0.02% |
| www.ggilbo.com | 1 | 0.02% |
| mhnse.com | 1 | 0.02% |
| www.omate.kr | 1 | 0.02% |
| www.newsedu.co.kr | 1 | 0.02% |
| www.sisaworld.kr | 1 | 0.02% |
| www.digitalasset.works | 1 | 0.02% |
| www.newsin.co.kr | 1 | 0.02% |
| www.newsworks.co.kr | 1 | 0.02% |
| www.fntoday.co.kr | 1 | 0.02% |
| www.newstapa.org | 1 | 0.02% |
| peoplepower21.org | 1 | 0.02% |
| www.mediajeju.com | 1 | 0.02% |
| www.weeklyseoul.net | 1 | 0.02% |
| topclass.chosun.com | 1 | 0.02% |
| www.wowtv.co.kr | 1 | 0.02% |
| www.financialpost.co.kr | 1 | 0.02% |
| m.seoul.co.kr | 1 | 0.02% |
| www.kfenews.co.kr | 1 | 0.02% |
| www.dronejournal.net | 1 | 0.02% |
| ujnews.co.kr | 1 | 0.02% |
| www.leadeconomy.co.kr | 1 | 0.02% |
| www.gokorea.kr | 1 | 0.02% |
| www.dongbangilbo.co.kr | 1 | 0.02% |
| mediahub.seoul.go.kr | 1 | 0.02% |
| www.nursenews.co.kr | 1 | 0.02% |
| www.addnewsin.com | 1 | 0.02% |
| www.engdaily.com | 1 | 0.02% |
| m.sedaily.com | 1 | 0.02% |
| cine21.com | 1 | 0.02% |
| www.sisa-news.com | 1 | 0.02% |
| www.imedialife.co.kr | 1 | 0.02% |
| www.joynews24.com | 1 | 0.02% |
| www.mediawatch.kr | 1 | 0.02% |
| www.ulsanilbo.co.kr | 1 | 0.02% |
| chosundaily.com | 1 | 0.02% |
| www.technologyreview.kr | 1 | 0.02% |
| www.paxetv.com | 1 | 0.02% |
| dailydental.co.kr | 1 | 0.02% |
| www.foodtoday.or.kr | 1 | 0.02% |
| www.thedailymoney.com | 1 | 0.02% |
| www.thescoop.co.kr | 1 | 0.02% |
| economist.co.kr | 1 | 0.02% |
| www.shippingnewsnet.com | 1 | 0.02% |
| www.techm.kr | 1 | 0.02% |
| radiokorea.com | 1 | 0.02% |
| thelec.kr | 1 | 0.02% |
| www.yangsanilbo.com | 1 | 0.02% |
| www.vanchosun.com | 1 | 0.02% |
| www.dentalarirang.com | 1 | 0.02% |
| car.withnews.kr | 1 | 0.02% |
| www.kstnews.co.kr | 1 | 0.02% |
| www.snunews.com | 1 | 0.02% |
| news.samsungcnt.com | 1 | 0.02% |
| www.newsthevoice.com | 1 | 0.02% |
| www.kukinews.com | 1 | 0.02% |
| www.cctoday.co.kr | 1 | 0.02% |
| m.dailian.co.kr | 1 | 0.02% |
| www.atlantajoongang.com | 1 | 0.02% |
| ccej.or.kr | 1 | 0.02% |
| www.snmnews.com | 1 | 0.02% |
| speedme.ru | 1 | 0.02% |
| www.jeongpil.com | 1 | 0.02% |
| mobile.busan.com | 1 | 0.02% |
| www.gjdream.com | 1 | 0.02% |
| theindigo.co.kr | 1 | 0.02% |
| www.freezinenews.com | 1 | 0.02% |
| www.mygoyang.com | 1 | 0.02% |
| www.mhns.co.kr | 1 | 0.02% |
| www.i-boss.co.kr | 1 | 0.02% |
| www.tech42.co.kr | 1 | 0.02% |
| www.cartvnews.com | 1 | 0.02% |
| www.popsci.co.kr | 1 | 0.02% |
| www.newsis.com | 1 | 0.02% |
| www.mixvale.com.br | 1 | 0.02% |
| www.outsourcing.co.kr | 1 | 0.02% |
| www.mhnse.com | 1 | 0.02% |
| www.news1.kr | 1 | 0.02% |
| www.viva100.com | 1 | 0.02% |
| news.tf.co.kr | 1 | 0.02% |
| www.bikem.co.kr | 1 | 0.02% |
| www.ccdailynews.com | 1 | 0.02% |
| www.iminju.net | 1 | 0.02% |
| snvision.seongnam.go.kr | 1 | 0.02% |
| www.elle.co.kr | 1 | 0.02% |
| www.esocialtimes.com | 1 | 0.02% |
| theviewers.co.kr | 1 | 0.02% |
| www.bundangnews.co.kr | 1 | 0.02% |
| www.efocus.co.kr | 1 | 0.02% |
| www.sportsworldi.com | 1 | 0.02% |
| www.cosmorning.com | 1 | 0.02% |
| www.koreaeaglenews.com | 1 | 0.02% |
| www.jnilbo.com | 1 | 0.02% |
| www.slist.kr | 1 | 0.02% |
| www.wikileaks-kr.org | 1 | 0.02% |
| www.kndaily.co.kr | 1 | 0.02% |
| heraldk.com | 1 | 0.02% |
| www.fetv.co.kr | 1 | 0.02% |
| www.sidae.com | 1 | 0.02% |
| www.akomnews.com | 1 | 0.02% |
| www.labortoday.co.kr | 1 | 0.02% |
| www.koreatimes.net | 1 | 0.02% |
| www.welfarenews.net | 1 | 0.02% |
| www.newsinstar.com | 1 | 0.02% |
| www.suwonilbo.kr | 1 | 0.02% |
| www.joongangenews.com | 1 | 0.02% |
| www.dispatch.co.kr | 1 | 0.02% |
| www.mdilbo.com | 1 | 0.02% |
| www.opinionnews.co.kr | 1 | 0.02% |
| www.dginclusion.com | 1 | 0.02% |
| www.enewstoday.co.kr | 1 | 0.02% |
| www.kwnews.co.kr | 1 | 0.02% |
| www.topdigital.com.au | 1 | 0.02% |
| www.naewoeilbo.com | 1 | 0.02% |
| www.newsverse.kr | 1 | 0.02% |
| www.newsnbook.com | 1 | 0.02% |
| www.benews.co.kr | 1 | 0.02% |
| www.kmjournal.net | 1 | 0.02% |
| alphabiz.co.kr | 1 | 0.02% |
| www.thebigdata.co.kr | 1 | 0.02% |
| digitalchosun.dizzo.com | 1 | 0.02% |
| www.insight.co.kr | 1 | 0.02% |
| www.gametoc.co.kr | 1 | 0.02% |
| www.issuevalley.com | 1 | 0.02% |
| game.donga.com | 1 | 0.02% |
| www.jeonpa.co.kr | 1 | 0.02% |
| kr.aving.net | 1 | 0.02% |
| www.sijung.co.kr | 1 | 0.02% |
| m.ddaily.co.kr | 1 | 0.02% |
| www.dongponews.net | 1 | 0.02% |
| www.smarttoday.co.kr | 1 | 0.02% |
| hnews.kr | 1 | 0.02% |
| www.obsnews.co.kr | 1 | 0.02% |
| www.brandbrief.co.kr | 1 | 0.02% |
| seoulpi.io | 1 | 0.02% |
| chaovietnam.co.kr | 1 | 0.02% |
| news.ikbc.co.kr | 1 | 0.02% |
| www.gugaktimes.com | 1 | 0.02% |
| www.dailynk.com | 1 | 0.02% |
| bravo.etoday.co.kr | 1 | 0.02% |
| www.aseandaily.co.kr | 1 | 0.02% |
| www.gbpolitics.com | 1 | 0.02% |
| m.snilbo.co.kr | 1 | 0.02% |
| www.thisisgame.com | 1 | 0.02% |
| www.mindlenews.com | 1 | 0.02% |
| www.autoherald.co.kr | 1 | 0.02% |
| kids.donga.com | 1 | 0.02% |
| www.yhtoday.co.kr | 1 | 0.02% |
| www.beminor.com | 1 | 0.02% |
| monthly.chosun.com | 1 | 0.02% |
| www.dailypharm.com | 1 | 0.02% |
| www.consumuch.com | 1 | 0.02% |
| www.ibric.org | 1 | 0.02% |
| www.eanews.kr | 1 | 0.02% |
| www.golfbiz.co.kr | 1 | 0.02% |
| www.boannews.com | 1 | 0.02% |
| www.incheonin.com | 1 | 0.02% |
| www.geconomy.co.kr | 1 | 0.02% |
| theguru.co.kr | 1 | 0.02% |

### 수집 category별 분포

| 항목 | article 수 | 비율 |
|---|---:|---:|
| general | 630 | 11.85% |
| nation | 624 | 11.74% |
| technology | 618 | 11.63% |
| business | 614 | 11.55% |
| world | 613 | 11.53% |
| entertainment | 564 | 10.61% |
| sports | 554 | 10.42% |
| health | 552 | 10.38% |
| science | 547 | 10.29% |

## 3. Field Completeness

`empty_string`은 정확히 빈 문자열, `whitespace_only`는 공백만 있는 문자열이다. `invalid_type`은 예상 타입이 아니다. 표의 분모는 전체 record다.

| 의미 필드 | missing | null | empty string | whitespace only | invalid type | 정상 값 |
|---|---:|---:|---:|---:|---:|---:|
| title | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5,316 (100.00%) |
| content | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5,316 (100.00%) |
| description | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5,316 (100.00%) |
| url | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5,316 (100.00%) |
| publishedAt | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5,316 (100.00%) |
| source | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 0 (0.00%) | 5,316 (100.00%) |

## 4. Content Length Distribution

- 유효 문자열 record 5,316건 기준: min 265, max 27993, mean 1311.79, median 1041.5자.
- 분위수: p10 265.0자, p25 441.75자, p75 1641.25자, p90 2464.0자, p95 3397.75자.
- 극단 길이(중첩 구간): under100 0건 (0.00%), under500 1,329건 (25.00%), over10000 11건 (0.21%), over20000 1건 (0.02%).
- 단일 non-empty line 콘텐츠 21건 (0.40%). 짧은 줄 구조 후보의 해석에 제한이 있다.

| GNews raw 그룹 | 기사 수 | min / median / max (자) | 500자 미만 | 생략 표식 후보 |
|---|---:|---|---:|---:|
| gnews_legacy | 1,329 | 265 / 266 / 267 | 1,329 (100.00%) | 0 |
| gnews_fullversion | 3,987 | 500 / 1295 / 27993 | 0 (0.00%) | 0 |

## 5. Duplicate Analysis

각 방법은 비어 있거나 결측인 비교값을 제외한다. `recordsInDuplicateGroups`는 중복 group에 속한 모든 record 수이며 초과 record 수와 구분한다. URL 정규화는 fragment, `utm_*`와 명시된 tracking parameter만 제거하고 raw URL을 변경하지 않았다. Near-obvious 두 방법은 **후보**다.

| 비교 기준 | group 수 | group 소속 record | 초과 record | 다른 raw 파일 | 다른 category | 다른 source |
|---|---:|---:|---:|---:|---:|---:|
| exactURL | 506 | 1,031 (19.39%) | 525 | 506 | 467 | 3 |
| normalizedURL | 506 | 1,031 (19.39%) | 525 | 506 | 467 | 3 |
| exactRawContentSHA256 | 523 | 1,068 (20.09%) | 545 | 462 | 458 | 9 |
| nearObviousWhitespaceContentSHA256 | 523 | 1,068 (20.09%) | 545 | 462 | 458 | 9 |
| nearObviousTitleAndLength | 534 | 1,191 (22.40%) | 657 | 457 | 450 | 25 |

## 6. Title Anomalies

반복 title은 원문 title의 공백만 접어 frequency를 계산했다. 첫 줄이 title처럼 보인다는 기준은 짧은 독립 첫 줄과 뒤의 더 긴 줄을 이용한 탐색 후보일 뿐 title 복구 근거가 아니다.

- empty_title: 0건 (0.00%), 영향 source 0개
- title_equals_source: 286건 (5.38%), 영향 source 3개
- very_short_title_8_chars: 251건 (4.72%), 영향 source 4개
- title_repeated_in_first_3_lines: 74건 (1.39%), 영향 source 11개
- different_headline_like_first_line: 1,071건 (20.15%), 영향 source 158개
- 3회 이상 반복 title: 44개 group; 30자 이하 또는 source와 같은 generic 반복 후보: 11개 group.

| 반복 title | frequency | 영향 source |
|---|---:|---|
| KBS 뉴스 | 243 | KBS 뉴스, news.kbs.co.kr |
| 연합뉴스 한민족센터 | 39 | koreancenter.or.kr, 연합뉴스 한민족센터 |
| 메디포뉴스 | 7 | 메디포뉴스 |
| 사람과 지역의 가치를 생각합니다. | 5 | 영남일보 |
| "전선도 배터리도 없다"…레이저로 로봇에 24시간 전력 공급 | 4 | v.daum.net, 지디넷코리아 |
| XRP, 13일 연속 ETF 자금 유입에도 가격 '역주행'..."공포 심리 극대화" | 4 | 글로벌이코노믹 |
| ‘관리 장인’ 박진영, 냉장고 공개…식재료에 ‘술렁’ | 4 | v.daum.net |
| “5개월만에 40% 폭락했네요”…야간 거래량 보면 더 공포스러운 비트코인 | 4 | v.daum.net, 매일경제 |
| 韓 연구진, “치매 진행막는 열쇠 발굴”…신경세포 살리고 기억력 높였다 | 4 | v.daum.net |
| 여에스더, 서울대 CC와 약혼-결혼 6달 전 파혼 | 4 | 미디어파인 |
| 트럼프 "베네수와 석유거래 합의…매장량 과반 통제권 확보" | 4 | 연합뉴스 |
| 홍석천 “4년 동거한 연인에 위자료…내 지인과 살더라” | 4 | 동아일보, 스포츠동아 |
| "양자컴퓨터, 이르면 2027년에 기존 암호 체계 무력화 가능" | 3 | 지디넷코리아 |
| "엄마 나 접는 폰 사줘" 했다간 큰일 나겠네…400만원까지 치솟는다 | 3 | v.daum.net, 아시아경제 |
| '425사업 피날레' 軍정찰 위성 5호기 모레 미국서 발사 | 3 | 한국일보 |
| '리벤지 드레스' 입은 다이애나비 밀랍 인형 파리서 공개 | 3 | 연합뉴스 |
| '북한 무인기 침투' 군경합동조사TF, 민간인 피의자 3명 압수수색 | 3 | MBC 뉴스 |
| '중국인이 망쳤다' 황희찬의 울버햄프턴 강등 "예견된 몰락... 미래가 더 문제" | 3 | v.daum.net |
| 30㎞ 상공서 스마트폰 낙하…5시간 만에 찾았더니 ‘멀쩡’ | 3 | v.daum.net, 지디넷코리아 |
| 5년 굶어도 살아남는 심해 초거대 괴물의 비밀 | 3 | v.daum.net |
| 80세에 50대 기억력 가진 이들, ‘이것’이 달랐다 | 3 | 헬스조선 |
| [건강포커스] "대마·코카인·암페타민 등 마약류, 뇌졸중 위험 크게 높여" | 3 | 네이트, 연합뉴스 |
| ‘지옥문 열리는 순간’ 고스란히…SNS가 전한 참사 현장 | 3 | v.daum.net |
| “나 헤르페스래” 남친 성병 고백에 “감염 무섭다”…전염력 어느 정도길래[라이프] | 3 | 서울신문 |
| “바퀴에서 시체썩는 냄새가”…도쿄발 항공기 바퀴 수납공간서 시신 발견 | 3 | 문화일보 |
| “월요일 삼전 주가 어떡해” CXMT 깜짝 어닝서프라이즈 | 3 | v.daum.net, 매일경제 |
| 강남은 3주째 빠지는데 외곽은 0.5%대↑···서울 집값 중심축 이동 | 3 | 시사저널e |
| 국립중앙과학관 전시물 출처가 나무위키?..."미처 확인 못 해" | 3 | YTN |
| 김민석, 부산서 국힘에 "이진숙 내쫓든지 아니면 YS사진 내려라" | 3 | MBC 뉴스, 연합뉴스 |
| 김주형, 투어 챔피언십 2R도 공동 15위…공동 선두와 5타차 | 3 | 문화일보, 연합뉴스 |

## 7. Repeated Prefix Patterns

첫 15개 non-empty line에서 관측된 후보 279개. 동일 anchor의 corpus/source/domain 범위 항목은 각각 별개 검토 행이다. 위치 수는 전체 콘텐츠의 disjoint prefix/middle/suffix 등장 횟수다.

| ID | 범위 | anchor | 기사 수 | 범위 내 비율 | 위치(prefix/middle/suffix) | 영향 source |
|---|---|---|---:|---:|---|---|
| CANDIDATE-0001 | corpus:전체 | 브라우저에서만 사용하실 수 있습니다. | 243 | 4.57% | 222/0/21 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0002 | corpus:전체 | 읽어주기 기능은 크롬기반의 | 243 | 4.57% | 243/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0003 | domain:news.kbs.co.kr | 브라우저에서만 사용하실 수 있습니다. | 243 | 100.00% | 222/0/21 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0004 | domain:news.kbs.co.kr | 읽어주기 기능은 크롬기반의 | 243 | 100.00% | 243/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0007 | source:KBS 뉴스 | 브라우저에서만 사용하실 수 있습니다. | 241 | 100.00% | 220/0/21 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0008 | source:KBS 뉴스 | 읽어주기 기능은 크롬기반의 | 241 | 100.00% | 241/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0013 | corpus:전체 | 기사 본문 영역 | 177 | 3.33% | 177/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0014 | domain:news.kbs.co.kr | 기사 본문 영역 | 177 | 72.84% | 177/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0015 | source:KBS 뉴스 | 기사 본문 영역 | 175 | 72.61% | 175/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0016 | corpus:전체 | ■ 제보하기 | 148 | 2.78% | 47/100/1 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0017 | domain:news.kbs.co.kr | ■ 제보하기 | 148 | 60.91% | 47/100/1 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0019 | corpus:전체 | ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 2.77% | 26/121/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0020 | corpus:전체 | ▷ 전화 : 02-781-1234, 4444 | 147 | 2.77% | 35/112/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0021 | corpus:전체 | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 147 | 2.77% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0022 | domain:news.kbs.co.kr | ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 60.49% | 26/121/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0023 | domain:news.kbs.co.kr | ▷ 전화 : 02-781-1234, 4444 | 147 | 60.49% | 35/112/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0024 | domain:news.kbs.co.kr | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 147 | 60.49% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0044 | source:KBS 뉴스 | ■ 제보하기 | 146 | 60.58% | 47/98/1 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0045 | source:KBS 뉴스 | ▷ 이메일 : kbs1234@kbs.co.kr | 145 | 60.17% | 26/119/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0046 | source:KBS 뉴스 | ▷ 전화 : 02-781-1234, 4444 | 145 | 60.17% | 35/110/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0047 | source:KBS 뉴스 | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 145 | 60.17% | 41/104/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0058 | corpus:전체 | [앵커] | 113 | 2.13% | 114/46/4 | KBS 뉴스, YTN, news.kbs.co.kr 외 2개 |
| CANDIDATE-0061 | corpus:전체 | Key Points | 96 | 1.81% | 64/0/32 | mk.co.kr, 매일경제 |
| CANDIDATE-0062 | domain:www.mk.co.kr | Key Points | 96 | 36.23% | 64/0/32 | mk.co.kr, 매일경제 |
| CANDIDATE-0063 | source:매일경제 | Key Points | 95 | 35.98% | 63/0/32 | mk.co.kr, 매일경제 |

## 8. Repeated Suffix Patterns

마지막 15개 non-empty line에서 관측된 후보 420개.

| ID | 범위 | anchor | 기사 수 | 범위 내 비율 | 위치(prefix/middle/suffix) | 영향 source |
|---|---|---|---:|---:|---|---|
| CANDIDATE-0010 | corpus:전체 | 관련기사 | 219 | 4.12% | 7/2/210 | zdnet.co.kr, 네이트, 뉴스웨이 외 4개 |
| CANDIDATE-0011 | domain:zdnet.co.kr | 관련기사 | 203 | 81.53% | 0/0/203 | zdnet.co.kr, 네이트, 뉴스웨이 외 4개 |
| CANDIDATE-0012 | source:지디넷코리아 | 관련기사 | 199 | 81.22% | 0/0/199 | zdnet.co.kr, 네이트, 뉴스웨이 외 4개 |
| CANDIDATE-0018 | corpus:전체 | 좋아요 | 148 | 2.78% | 0/1/147 | KBS 뉴스, news.kbs.co.kr, 쿠키뉴스 |
| CANDIDATE-0037 | corpus:전체 | 응원해요 | 147 | 2.77% | 0/0/147 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0038 | corpus:전체 | 이 기사가 좋으셨다면 | 147 | 2.77% | 0/1/146 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0039 | corpus:전체 | 후속 원해요 | 147 | 2.77% | 0/0/147 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0040 | domain:news.kbs.co.kr | 응원해요 | 147 | 60.49% | 0/0/147 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0041 | domain:news.kbs.co.kr | 이 기사가 좋으셨다면 | 147 | 60.49% | 0/1/146 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0042 | domain:news.kbs.co.kr | 좋아요 | 147 | 60.49% | 0/1/146 | KBS 뉴스, news.kbs.co.kr, 쿠키뉴스 |
| CANDIDATE-0043 | domain:news.kbs.co.kr | 후속 원해요 | 147 | 60.49% | 0/0/147 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0054 | source:KBS 뉴스 | 응원해요 | 145 | 60.17% | 0/0/145 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0055 | source:KBS 뉴스 | 이 기사가 좋으셨다면 | 145 | 60.17% | 0/1/144 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0056 | source:KBS 뉴스 | 좋아요 | 145 | 60.17% | 0/1/144 | KBS 뉴스, news.kbs.co.kr, 쿠키뉴스 |
| CANDIDATE-0057 | source:KBS 뉴스 | 후속 원해요 | 145 | 60.17% | 0/0/145 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0059 | corpus:전체 | <저작권자 © 스타뉴스, 무단전재 및 재배포 금지> | 113 | 2.13% | 0/0/113 | starnewskorea.com, 스타뉴스 |
| CANDIDATE-0060 | domain:www.starnewskorea.com | <저작권자 © 스타뉴스, 무단전재 및 재배포 금지> | 113 | 90.40% | 0/0/113 | starnewskorea.com, 스타뉴스 |
| CANDIDATE-0094 | corpus:전체 | 실시간 뜨거운 관심을 받고 있는 뉴스 | 69 | 1.30% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0095 | corpus:전체 | 오늘의 핫 클릭 | 69 | 1.30% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0096 | domain:news.kbs.co.kr | 실시간 뜨거운 관심을 받고 있는 뉴스 | 69 | 28.40% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0097 | domain:news.kbs.co.kr | 오늘의 핫 클릭 | 69 | 28.40% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0098 | source:KBS 뉴스 | 실시간 뜨거운 관심을 받고 있는 뉴스 | 69 | 28.63% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0099 | source:KBS 뉴스 | 오늘의 핫 클릭 | 69 | 28.63% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0102 | corpus:전체 | <저작권자 (c) 연합인포맥스, 무단전재 및 재배포 금지, AI 학습 및 활용 금지> | 67 | 1.26% | 0/0/67 | news.einfomax.co.kr, 연합인포맥스 |
| CANDIDATE-0103 | domain:news.einfomax.co.kr | <저작권자 (c) 연합인포맥스, 무단전재 및 재배포 금지, AI 학습 및 활용 금지> | 67 | 82.72% | 0/0/67 | news.einfomax.co.kr, 연합인포맥스 |

## 9. Repeated Block Candidates

공백만 정규화한 인접 non-empty line 2~3줄 후보 470개. 같은 URL 또는 동일 본문 반복 저장만으로 발생한 조합은 distinct identity/content 조건에서 제외했다. 경계 밖에서만 관측된 단일 줄 후보 9개는 JSON에 별도 수록했다.

| ID | 범위 | anchor | 기사 수 | 범위 내 비율 | 위치(prefix/middle/suffix) | 영향 source |
|---|---|---|---:|---:|---|---|
| CANDIDATE-0005 | corpus:전체 | 읽어주기 기능은 크롬기반의 / 브라우저에서만 사용하실 수 있습니다. | 243 | 4.57% | 243/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0006 | domain:news.kbs.co.kr | 읽어주기 기능은 크롬기반의 / 브라우저에서만 사용하실 수 있습니다. | 243 | 100.00% | 243/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0009 | source:KBS 뉴스 | 읽어주기 기능은 크롬기반의 / 브라우저에서만 사용하실 수 있습니다. | 241 | 100.00% | 241/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0025 | corpus:전체 | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 147 | 2.77% | 47/100/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0026 | corpus:전체 | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 147 | 2.77% | 47/100/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0027 | corpus:전체 | ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 2.77% | 35/112/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0028 | corpus:전체 | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 147 | 2.77% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0029 | corpus:전체 | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 2.77% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0030 | corpus:전체 | 이 기사가 좋으셨다면 / 좋아요 | 147 | 2.77% | 0/1/146 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0031 | domain:news.kbs.co.kr | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 147 | 60.49% | 47/100/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0032 | domain:news.kbs.co.kr | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 147 | 60.49% | 47/100/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0033 | domain:news.kbs.co.kr | ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 60.49% | 35/112/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0034 | domain:news.kbs.co.kr | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 147 | 60.49% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0035 | domain:news.kbs.co.kr | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 60.49% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0036 | domain:news.kbs.co.kr | 이 기사가 좋으셨다면 / 좋아요 | 147 | 60.49% | 0/1/146 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0048 | source:KBS 뉴스 | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 145 | 60.17% | 47/98/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0049 | source:KBS 뉴스 | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 145 | 60.17% | 47/98/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0050 | source:KBS 뉴스 | ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 145 | 60.17% | 35/110/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0051 | source:KBS 뉴스 | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 145 | 60.17% | 41/104/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0052 | source:KBS 뉴스 | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 145 | 60.17% | 41/104/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0053 | source:KBS 뉴스 | 이 기사가 좋으셨다면 / 좋아요 | 145 | 60.17% | 0/1/144 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0068 | corpus:전체 | AI 해설 기사 / AI 해설은 뉴스의 풍부한 이해를 위한 콘텐츠로, 기사 본문과 표현에 차이가 있을 수 있습니다. 정확한 내용은 기사 본문을 함께 확인해 주시기 바랍니다. | 89 | 1.67% | 89/0/0 | mk.co.kr, 매일경제 |
| CANDIDATE-0069 | domain:www.mk.co.kr | AI 해설 기사 / AI 해설은 뉴스의 풍부한 이해를 위한 콘텐츠로, 기사 본문과 표현에 차이가 있을 수 있습니다. 정확한 내용은 기사 본문을 함께 확인해 주시기 바랍니다. | 89 | 33.58% | 89/0/0 | mk.co.kr, 매일경제 |
| CANDIDATE-0072 | source:매일경제 | AI 해설 기사 / AI 해설은 뉴스의 풍부한 이해를 위한 콘텐츠로, 기사 본문과 표현에 차이가 있을 수 있습니다. 정확한 내용은 기사 본문을 함께 확인해 주시기 바랍니다. | 88 | 33.33% | 88/0/0 | mk.co.kr, 매일경제 |
| CANDIDATE-0077 | corpus:전체 | ▷ 이메일 : kbs1234@kbs.co.kr / ▷ 유튜브, 네이버, 카카오에서도 KBS뉴스를 구독해주세요! | 83 | 1.56% | 16/67/0 | KBS 뉴스 |

## 10. Suspicious AI / Non-article Content

관측된 단서별 후보 group 9개, 합집합 145건 (2.73%). 단서 문자열만으로 AI 생성 여부나 비기사 여부를 판단할 수 없다.

| 단서/구조 | 기사 수 | 영향 source | 영향 domain | 대표 identifier |
|---|---:|---|---|---|
| multiple_explanatory_format_markers | 61 (1.15%) | 2개 | 1개 | data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-01/26/science.json#articles[3] |
| observed_cue:AI 해설 | 89 (1.67%) | 2개 | 1개 | ArticleLocal-KG/data/raw/gnews-data/20260824T011237+0900/gnews/raw/010_top-headlines_coverage-… |
| observed_cue:Glossary | 61 (1.15%) | 2개 | 1개 | data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-01/26/science.json#articles[3] |
| observed_cue:Key Points | 96 (1.81%) | 2개 | 1개 | ArticleLocal-KG/data/raw/gnews-data/20260824T011237+0900/gnews/raw/010_top-headlines_coverage-… |
| observed_cue:Timeline | 60 (1.13%) | 1개 | 1개 | data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-01/26/science.json#articles[3] |
| observed_cue:세 줄 요약 | 35 (0.66%) | 1개 | 1개 | ArticleLocal-KG/data/raw/gnews-data/20260824T011237+0900/gnews/raw/007_top-headlines_coverage-… |
| observed_cue:인공지능이 자동으로 | 29 (0.55%) | 1개 | 1개 | ArticleLocal-KG/data/raw/gnews-data/20260824T011237+0900/gnews/raw/007_top-headlines_coverage-… |
| observed_cue:주요 용어 해설 | 61 (1.15%) | 2개 | 1개 | data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-01/26/science.json#articles[3] |
| short_repeated_line_dominant_content | 33 (0.62%) | 6개 | 7개 | ArticleLocal-KG/data/raw/gnews-data/20260824T011237+0900/gnews/raw/010_top-headlines_coverage-… |

### 제한된 대표 사례

서로 다른 주요 source에서 한 후보씩 골랐다. 아래는 기사 전문이 아닌 첫/끝 3줄과 anchor 주변 문맥이다. 각 후보의 짧은·중앙 길이·긴 사례 등은 JSON `representativeArticles`에 있다.

**CANDIDATE-0001 · 브라우저에서만 사용하실 수 있습니다.** — 243건, KBS 뉴스

대표: `data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2025-11/14/nation.json#articles[0]`; title `KBS 뉴스`; 원문 1,410자.

첫 줄: “퇴사 통보 안 했으니 180만 원 물어내”…강남 유명 치과 논란 [잇슈#태그] / 읽어주기 기능은 크롬기반의 / 브라우저에서만 사용하실 수 있습니다.

끝 줄: 0 / 오늘의 핫 클릭 / 실시간 뜨거운 관심을 받고 있는 뉴스

anchor 주변: “퇴사 통보 안 했으니 180만 원 물어내”…강남 유명 치과 논란 [잇슈#태그] / 읽어주기 기능은 크롬기반의 / 브라우저에서만 사용하실 수 있습니다. / 서울 강남의 한 유명 치과가 입사 이틀 만에 그만둔 직원에게 손해배상을 요구한 사실이 알려지며 논란이 일고 있습니다. / 해당 치과에 채용된 A 씨는 출근 첫날 면접 때 들었던 업무와 다른 일을 지시받았는데요.

**CANDIDATE-0010 · 관련기사** — 219건, 지디넷코리아

대표: `data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-03/08/technology.json#articles[0]`; title `OLED·터치 탑재 맥북 나온다…"명칭은 맥북 울트라"`; 원문 1,318자.

첫 줄: 애플이 OLED 디스플레이와 터치스크린을 탑재한 새로운 ‘맥북 울트라’ 모델을 올해 선보일 가능성이 제기됐다. / 블룸버그 통신은 8일(현지시간) 파워온 뉴스레터를 통해 애플이 완전히 새로운 형태의 맥북 모델을 준비 중이라고 보도했다. 파워온은 블룸버그 IT 전문기자인 마크 거먼이 운영하는 뉴스레터다. / 그 동안 업계에서는 애플이 올해 4분기 ▲OLED 디스플레이 ▲터치스크린 기능 ▲더 얇아진 디자인을 갖춘 M6 기반 맥북 프로를 출시할 것이라는 전망이 우세했다. 그러나 거먼은 해당 제품이 맥북 프로 후속 모델이 아니라 완전히 새로운 제품군일 가능성이 있다고 전했다.

끝 줄: 애플, 프리미엄 제품 강화…에어팟·아이폰에도 적용 / 이 같은 흐름은 올해에도 이어질 것으로 보인다. 약 2000달러 가격대로 예상되는 폴더블 아이폰은 대형 내부 디스플레이와 디스플레이 아래 센서를 탑재할 것으로 전망된다. 또한 에어팟 프로보다 더 높은 가격대의 새로운 에어팟도 개발 중이며, 이 제품은 컴퓨터 비전 카메라를 통해 시리에 시각 기반 지능 데이터를 제공할 것으… / 거먼은 애플이 기존 ‘맥북 프로’ 명칭을 유지할 가능성도 있지만, ‘맥북 울트라’라는 이름을 사용할 경우 제품이 라인업 최상위에 위치한다는 점을 보다 명확히 보여줄 수 있을 것이라고 설명했다. 그는 해당 제품이 올해 말 출시될 것으로 예상했다.

anchor 주변: 가격 역시 상당히 높을 것으로 예상된다. 거먼은 애플이 2017년 아이폰X와 2024년 아이패드 프로에 OLED 디스플레이를 도입하면서 제품 가격을 약 20% 인상했던 사례를 언급했다. 그는 맥북에 처음으로 OLED 디스플레이가 적용될 경우 유사한 수준의 가격 인상이 이뤄질 가능성이 있으며, 이를 통해 맥북 프로 라인업… / 또한 그는 이러한 전략이 애플의 전반적인 제품 라인업 확장 전략의 일부라고 덧붙였다. 애플은 최근 599달러라는 전례 없는 가격의 ‘맥북 네오’를 출시해 저가형 윈도 노트북과 크롬북 시장을 공략하는 등 보다 다양한 가격대의 제품을 제공하고 있다. 동시에 고급 제품군에서도 더 다양한 프리미엄 옵션을 선보이며 시장을 세분화… / 관련기사 / 애플, 프리미엄 제품 강화…에어팟·아이폰에도 적용 / 이 같은 흐름은 올해에도 이어질 것으로 보인다. 약 2000달러 가격대로 예상되는 폴더블 아이폰은 대형 내부 디스플레이와 디스플레이 아래 센서를 탑재할 것으로 전망된다. 또한 에어팟 프로보다 더 높은 가격대의 새로운 에어팟도 개발 중이며, 이 제품은 컴퓨터 비전 카메라를 통해 시리에 시각 기반 지능 데이터를 제공할 것으…

**CANDIDATE-0059 · <저작권자 © 스타뉴스, 무단전재 및 재배포 금지>** — 113건, 스타뉴스

대표: `data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2025-12/28/entertainment.json#articles[1]`; title `연말엔 르세라핌! K팝 그룹 유일 美 최대 규모 새해맞이 라이브 쇼 출연 '기대 UP'`; 원문 1,216자.

첫 줄: 그룹 르세라핌(LE SSERAFIM)이 미국 최대 규모의 새해맞이 라이브 쇼 출연을 앞두고 국내외 팬들의 기대를 모으고 있다. 최근 연말 특집 방송에서 선보인 무대들이 호평받으며 올해 마지막을 장식할 퍼포먼스에 뜨거운 관심이 쏠리고 있다. / 앞서 르세라핌(김채원, 사쿠라, 허윤진, 카즈하, 홍은채)은 31일(현지 시간) 미국 ABC에서 생방송되는 '딕 클라크스 뉴 이어스 로킹 이브 위드 라이언 시크레스트 2026'(Dick Clark's New Year's Rockin' Eve with Ryan Seacrest 2026, 이하 '뉴 이어스 로킹 이브') 출… / 르세라핌은 소속사 쏘스뮤직을 통해 "2025년 마지막 날 특별한 무대에 서게 돼 정말 설렌다. 많은 분들과 함께 한 해를 마무리하고 새해를 맞이한다는 게 무척 뜻깊다. 특히 올해는 발표한 노래들도 큰 사랑을 받았고 첫 월드투어도 돌아서 정말 행복했던 것 같다"라는 출연 소감을 전했다. 이어 "응원해 주신 모든 분들께 감…

끝 줄: 르세라핌은 '뉴 이어스 로킹 이브'에서 미니 4집 타이틀곡 'CRAZY'와 'SPAGHETTI (feat. j-hope of BTS)' 무대를 펼칠 예정이다. 이번 공연을 통해 전 세계 시청자들에게 팀의 퍼포먼스 역량을 강렬하게 각인시킬 계획이다. / 한편 르세라핌은 '뉴 이어스 로킹 이브'를 통해 2025년의 활동을 마무리한 이후 오는 26년 1월 31일~2월 1일 서울 잠실 실내체육관에서 월드투어의 앙코르 콘서트를 개최한다. 해당 공연은 일반 예매 10분 만에 2회차 모두 전석 매진됐다. / <저작권자 © 스타뉴스, 무단전재 및 재배포 금지>

anchor 주변: 르세라핌은 '뉴 이어스 로킹 이브'에서 미니 4집 타이틀곡 'CRAZY'와 'SPAGHETTI (feat. j-hope of BTS)' 무대를 펼칠 예정이다. 이번 공연을 통해 전 세계 시청자들에게 팀의 퍼포먼스 역량을 강렬하게 각인시킬 계획이다. / 한편 르세라핌은 '뉴 이어스 로킹 이브'를 통해 2025년의 활동을 마무리한 이후 오는 26년 1월 31일~2월 1일 서울 잠실 실내체육관에서 월드투어의 앙코르 콘서트를 개최한다. 해당 공연은 일반 예매 10분 만에 2회차 모두 전석 매진됐다. / <저작권자 © 스타뉴스, 무단전재 및 재배포 금지>

**CANDIDATE-0061 · Key Points** — 96건, 매일경제

대표: `data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-07/28/world.json#articles[2]`; title `“내가 항상 그에게 갔다, 권력은”…미국 차기 대권주자 과거 불륜女 ‘폭로’`; 원문 5,560자.

첫 줄: AI 해설 기사 / AI 해설은 뉴스의 풍부한 이해를 위한 콘텐츠로, 기사 본문과 표현에 차이가 있을 수 있습니다. 정확한 내용은 기사 본문을 함께 확인해 주시기 바랍니다. / 20년 전 불륜 폭로, 차기 대권주자 개빈 뉴섬에 닥친 ‘과거’

끝 줄: 정치인이나 고위 공직자의 업무를 돕는 사람을 말해요. 의원 사무실에서 일하거나, 개인적인 정책 비서 역할을 수행하는 등 다양한 임무를 맡죠. 보좌관은 해당 인물의 일정 관리, 자료 조사, 의사 전달 등 실무적인 부분을 지원하며, 때로는 중요한 정책 결정 과정에 조언을 하기도 해요. 기사에서는 루비 리피가 개빈 뉴섬 당시… / 회고록 / 자신의 과거 경험이나 삶을 되돌아보며 기록한 책을 의미해요. 일반적으로 개인의 중요한 사건, 만남, 생각 등을 시간 순서대로 정리하여 독자들에게 전달하는 형식이에요. 회고록은 종종 자신의 경험을 객관적으로 평가하거나, 특정 사건에 대한 자신의 입장을 밝히는 데 사용되기도 하죠. 최근 뉴섬 주지사가 펴낸 회고록에서 리피와…

anchor 주변: AI 해설은 뉴스의 풍부한 이해를 위한 콘텐츠로, 기사 본문과 표현에 차이가 있을 수 있습니다. 정확한 내용은 기사 본문을 함께 확인해 주시기 바랍니다. / 20년 전 불륜 폭로, 차기 대권주자 개빈 뉴섬에 닥친 ‘과거’ / Key Points / 미국 민주당의 유력 차기 대권주자로 꼽히는 개빈 뉴섬 캘리포니아 주지사의 20년 전 불륜 상대였던 루비 리피가 최근 뉴욕타임스(NYT)를 통해 당시의 부적절했던 관계를 상세히 공개하며 과거사가 다시 수면 위로 떠올랐어요. 📅 / 리피는 2005년 여름부터 당시 샌프란시스코 시장이었던 뉴섬 주지사와 관계를 맺었으며, 자신은 유부녀였던 상황을 언급하며 '권력은 강요할 필요 없이 존재하기만 하면 된다'는 말로 권력의 책임론을 제기했어요. ⚖️

**CANDIDATE-0102 · <저작권자 (c) 연합인포맥스, 무단전재 및 재배포 금지, AI 학습 및 활용 금지>** — 67건, 연합인포맥스

대표: `data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-05/26/business.json#articles[3]`; title `롯데손보 '운명의 날'…경영개선안 조건부 승인으로 고비 넘나`; 원문 1,750자.

첫 줄: (서울=연합인포맥스) 이윤구 이수용 기자 = 금융당국으로부터 경영개선요구를 받은 롯데손해보험의 경영개선계획 승인 여부가 27일 결정된다. / 금융당국과 보험업권에 따르면 금융위원회는 이날 정례회의를 열어 롯데손보가 제출한 경영개선계획 승인 여부를 의결한다. / 보험업계에서는 유상증자 등 금융당국이 원하는 수준의 자본확충 방안이 담기지 않은 만큼 롯데손보가 연내 매각 완료를 전제로 조건부 승인을 받을 가능성에 무게를 두고 있다.

끝 줄: yglee2@yna.co.kr / sylee3@yna.co.kr / <저작권자 (c) 연합인포맥스, 무단전재 및 재배포 금지, AI 학습 및 활용 금지>

anchor 주변: yglee2@yna.co.kr / sylee3@yna.co.kr / <저작권자 (c) 연합인포맥스, 무단전재 및 재배포 금지, AI 학습 및 활용 금지>

**CANDIDATE-0147 · 기자구독** — 52건, edaily.co.kr

대표: `data/raw/gnews-data/fullversion/20260830T124150+0900/raw/2026-03/17/business.json#articles[1]`; title `로킷헬스케어, AI 신장 질환 예측 솔루션 美 라이선스 아웃 계약`; 원문 1,653자.

첫 줄: 박정수 기자 / 기자구독 / [이데일리 박정수 기자] 인공지능(AI) 초개인화 장기 재생 플랫폼 전문기업 로킷헬스케어(376900)가 지난 17일 자사의 AI 신장 질환 예측 솔루션인 ‘AI Kidney’에 대해 미국 시장 진출을 위한 인증을 완료하고 상용화 라이선스 아웃 계약을 체결했다고 18일 밝혔다. 해당 솔루션은 다음 달 미국에서 정식 상용…

끝 줄: 당신을 위한 / 맞춤 뉴스by Dable / 소셜 댓글

anchor 주변: 박정수 기자 / 기자구독 / [이데일리 박정수 기자] 인공지능(AI) 초개인화 장기 재생 플랫폼 전문기업 로킷헬스케어(376900)가 지난 17일 자사의 AI 신장 질환 예측 솔루션인 ‘AI Kidney’에 대해 미국 시장 진출을 위한 인증을 완료하고 상용화 라이선스 아웃 계약을 체결했다고 18일 밝혔다. 해당 솔루션은 다음 달 미국에서 정식 상용… / 업계에서는 이를 로킷헬스케어가 AI 기반 장기 재생 플랫폼 기업에 ‘글로벌 AI 장기진단 예측 솔루션을 성공적으로 융합하며 AI 장기 진단, 재생 플랫폼이 수익 국면에 진입한 것으로 평가한다. 또한 이번 계약은 단순한 기술 수출을 넘어, 파격적인 수익 구조를 확보했다는 점에서 AI 진단 업계의 관심을 끌고 있다.


## 11. Source-specific Structural Findings

- 전체 범위 반복 후보 399개; 한 source에서만 관측된 범위 후보 198개; 한 domain에서만 관측된 범위 후보 297개.
- 아래는 source 한정 후보의 상위 사례다. `scopeRatio`는 해당 source의 전체 raw record 수가 분모다.

| ID | 범위 | anchor | 기사 수 | 범위 내 비율 | 위치(prefix/middle/suffix) | 영향 source |
|---|---|---|---:|---:|---|---|
| CANDIDATE-0076 | source:KBS 뉴스 | ▷ 유튜브, 네이버, 카카오에서도 KBS뉴스를 구독해주세요! | 83 | 34.44% | 9/74/0 | KBS 뉴스 |
| CANDIDATE-0081 | source:KBS 뉴스 | ▷ 이메일 : kbs1234@kbs.co.kr / ▷ 유튜브, 네이버, 카카오에서도 KBS뉴스를 구독해주세요! | 83 | 34.44% | 16/67/0 | KBS 뉴스 |
| CANDIDATE-0082 | source:KBS 뉴스 | ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr / ▷ 유튜브, 네이버, 카카오에서도 KBS뉴스를 구독해주세요! | 83 | 34.44% | 21/62/0 | KBS 뉴스 |
| CANDIDATE-0093 | source:KBS 뉴스 | 오늘의 핫 클릭 / 실시간 뜨거운 관심을 받고 있는 뉴스 | 69 | 28.63% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0098 | source:KBS 뉴스 | 실시간 뜨거운 관심을 받고 있는 뉴스 | 69 | 28.63% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0099 | source:KBS 뉴스 | 오늘의 핫 클릭 | 69 | 28.63% | 0/0/69 | KBS 뉴스 |
| CANDIDATE-0211 | source:KBS 뉴스 | 연합뉴스 | 36 | 14.94% | 0/34/2 | KBS 뉴스 |
| CANDIDATE-0216 | source:연합뉴스 | 세 줄 요약 | 35 | 10.12% | 35/0/0 | 연합뉴스 |
| CANDIDATE-0218 | source:코인리더스 | *면책 조항: 이 기사는 투자 참고용으로 이를 근거로 한 투자 손실에 대해 책임을 지지 않습니다. 해당 내용은 정보 제공의 목적으로만 해석되어야 합니다.* | 34 | 91.89% | 0/0/34 | 코인리더스 |
| CANDIDATE-0224 | source:뉴스핌 | [뉴스핌 베스트 기사] | 32 | 47.06% | 12/0/20 | 뉴스핌 |
| CANDIDATE-0232 | source:메디컬투데이 | "이 기사는 메디컬투데이와 아임닥터가 엄선한 의료인 및 의대생 자문기자단이 검토 및 작성하였습니다. 건강한 선택을 돕기 위해 신뢰할 수 있는 의학 정보만을 전해드립니다." | 26 | 100.00% | 26/0/0 | 메디컬투데이 |
| CANDIDATE-0296 | source:메디컬투데이 | [저작권자ⓒ 메디컬투데이. 무단전재-재배포 금지] | 23 | 88.46% | 0/0/23 | 메디컬투데이 |
| CANDIDATE-0303 | source:YTN | [전화] 02-398-8585 / [메일] social@ytn.co.kr | 22 | 26.19% | 0/0/22 | YTN |
| CANDIDATE-0304 | source:YTN | [카카오톡] YTN 검색해 채널 추가 / [전화] 02-398-8585 | 22 | 26.19% | 0/0/22 | YTN |
| CANDIDATE-0305 | source:YTN | [카카오톡] YTN 검색해 채널 추가 / [전화] 02-398-8585 / [메일] social@ytn.co.kr | 22 | 26.19% | 0/0/22 | YTN |
| CANDIDATE-0312 | source:YTN | [메일] social@ytn.co.kr | 22 | 26.19% | 0/0/22 | YTN |
| CANDIDATE-0313 | source:YTN | [전화] 02-398-8585 | 22 | 26.19% | 0/0/22 | YTN |
| CANDIDATE-0314 | source:YTN | [카카오톡] YTN 검색해 채널 추가 | 22 | 26.19% | 0/0/22 | YTN |
| CANDIDATE-0329 | source:아시아경제 | <ⓒ투자가를 위한 경제콘텐츠 플랫폼, 아시아경제. 무단전재 배포금지, AI 학습 및 활용 금지> | 18 | 20.22% | 0/0/18 | 아시아경제 |
| CANDIDATE-0341 | source:YTN | [메일] social@ytn.co.kr / [저작권자(c) YTN 무단전재, 재배포 및 AI 데이터 활용 금지] | 16 | 19.05% | 0/0/16 | YTN |

### Domain 한정 후보

동일 anchor가 한 URL domain에서만 관측된 후보의 상위 사례다. domain 범위 비율은 그 domain의 전체 raw record 수가 분모다.

| ID | 범위 | anchor | 기사 수 | 범위 내 비율 | 위치(prefix/middle/suffix) | 영향 source |
|---|---|---|---:|---:|---|---|
| CANDIDATE-0003 | domain:news.kbs.co.kr | 브라우저에서만 사용하실 수 있습니다. | 243 | 100.00% | 222/0/21 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0004 | domain:news.kbs.co.kr | 읽어주기 기능은 크롬기반의 | 243 | 100.00% | 243/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0006 | domain:news.kbs.co.kr | 읽어주기 기능은 크롬기반의 / 브라우저에서만 사용하실 수 있습니다. | 243 | 100.00% | 243/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0014 | domain:news.kbs.co.kr | 기사 본문 영역 | 177 | 72.84% | 177/0/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0017 | domain:news.kbs.co.kr | ■ 제보하기 | 148 | 60.91% | 47/100/1 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0022 | domain:news.kbs.co.kr | ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 60.49% | 26/121/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0023 | domain:news.kbs.co.kr | ▷ 전화 : 02-781-1234, 4444 | 147 | 60.49% | 35/112/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0024 | domain:news.kbs.co.kr | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 147 | 60.49% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0031 | domain:news.kbs.co.kr | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 | 147 | 60.49% | 47/100/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0032 | domain:news.kbs.co.kr | ■ 제보하기 / ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 147 | 60.49% | 47/100/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0033 | domain:news.kbs.co.kr | ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 60.49% | 35/112/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0034 | domain:news.kbs.co.kr | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 | 147 | 60.49% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0035 | domain:news.kbs.co.kr | ▷ 카카오톡 : 'KBS제보' 검색, 채널 추가 / ▷ 전화 : 02-781-1234, 4444 / ▷ 이메일 : kbs1234@kbs.co.kr | 147 | 60.49% | 41/106/0 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0036 | domain:news.kbs.co.kr | 이 기사가 좋으셨다면 / 좋아요 | 147 | 60.49% | 0/1/146 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0040 | domain:news.kbs.co.kr | 응원해요 | 147 | 60.49% | 0/0/147 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0041 | domain:news.kbs.co.kr | 이 기사가 좋으셨다면 | 147 | 60.49% | 0/1/146 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0043 | domain:news.kbs.co.kr | 후속 원해요 | 147 | 60.49% | 0/0/147 | KBS 뉴스, news.kbs.co.kr |
| CANDIDATE-0060 | domain:www.starnewskorea.com | <저작권자 © 스타뉴스, 무단전재 및 재배포 금지> | 113 | 90.40% | 0/0/113 | starnewskorea.com, 스타뉴스 |
| CANDIDATE-0062 | domain:www.mk.co.kr | Key Points | 96 | 36.23% | 64/0/32 | mk.co.kr, 매일경제 |
| CANDIDATE-0066 | domain:www.mk.co.kr | AI 해설 기사 | 89 | 33.58% | 89/0/0 | mk.co.kr, 매일경제 |

## 12. Unknown / Difficult Cases

- 파싱 실패 파일 0개; 상세 경로와 오류는 JSON `parseErrors` 참조.
- URL domain 결측/형식 오류 0건; category 미해결/결측 0건.
- 원문 끝 생략 표식 후보 0건. 실제 잘림 여부는 여기서 확정하지 않는다.
- 공백 정규화만 사용하므로 문장 변형, 유사 표현, HTML/메타 조합을 합치지 않는다. 아주 짧은 source별 분모와 중복 저장은 frequency 해석 시 확인이 필요하다.
- 이번 범위는 GNews `articles` row로 한정한다. SSAFY·Pilot·GDELT는 수치와 후보에 포함하지 않았다.

## 13. Recommendations for Next Audit Step

1. JSON의 반복 anchor별 최대 4개 대표 identifier와 공통 `representativeArticles` 발췌에서 실제 기사 본문과 UI/저작권/요약 영역의 경계를 사람이 확인한다.
2. source 한정 후보는 source 이름뿐 아니라 domain, 파일, category 간 일관성을 검토한다.
3. URL/content 중복 group과 반복 title group의 대표 identifier를 비교해 반복 저장 효과를 분리한다.
4. AI/설명 형식 및 짧은 meta/UI 우세 후보를 별도 원문 표본으로 확인한 뒤 정책 catalog를 설계한다.

## Audit method

`python3 scripts/audit_news_corpus.py --project-root .`으로 동일한 Markdown/JSON을 재생성한다. 줄 anchor는 공백 정규화 후 최대 220자, 반복 block은 인접 2~3 non-empty line이다. 후보는 3개 이상 record, 3개 이상 URL/content identity 및 3개 이상 서로 다른 공백 정규화 content hash를 요구한다. 첫/끝 15줄에 전혀 나타나지 않는 middle-only 후보는 10개 record와 8개 content hash를 요구한다. source/domain 범위는 해당 범위 article의 10% 이상, 전체 범위는 5개 이상 record를 요구한다. URL 또는 내용 hash가 동일한 record를 전처리하거나 제거하지 않았다. JSON은 article identifier별 공통 대표 발췌(첫/끝 15줄)와 후보별 anchor ±2줄만 담았다.
