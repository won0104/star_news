#!/usr/bin/env python3
"""GNews 평가 원본을 별빛 뉴스 통합 목업 데이터로 변환한다.

이 스크립트는 외부 API나 모델을 호출하지 않는다. 실제 GNews 기사 294건은
원문 링크와 출처를 보존하고, 재현 가능한 규칙으로 서비스 카테고리를 분류한다.
카테고리별 시연량과 3개월 사용자 기록에 필요한 보강 데이터는 명시적으로
``synthetic=true``를 붙여 생성한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Any


SOURCE_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MOCKUP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    SOURCE_REPOSITORY_ROOT
    / "ArticleLocal-KG"
    / "data"
    / "raw"
    / "gnews-data"
    / "20260824T011237+0900"
    / "gnews"
    / "normalized_articles.jsonl"
)
DEFAULT_METADATA = (
    SOURCE_REPOSITORY_ROOT
    / "ArticleLocal-KG"
    / "data"
    / "raw"
    / "evaluation"
    / "runs"
    / "20260824T011237+0900"
    / "run_metadata.json"
)
DEFAULT_OUTPUT = MOCKUP_ROOT / "data" / "mock"
MIN_CURRENT_ARTICLES_PER_CATEGORY = 24
RANDOM_SEED = 20260824
KST = timezone(timedelta(hours=9))


HOME_TREND_PERIODS = [
    {
        "id": "today",
        "label": "오늘",
        "title": "오늘 주요 흐름",
        "window_days": 1,
        "window_label": "오늘",
        "comparison_label": "전일 대비",
        "volume_multiplier": 1.0,
    },
    {
        "id": "week",
        "label": "1주",
        "title": "이번 주 주요 흐름",
        "window_days": 7,
        "window_label": "최근 1주",
        "comparison_label": "직전 1주 대비",
        "volume_multiplier": 2.4,
    },
    {
        "id": "month",
        "label": "1개월",
        "title": "한 달간 주요 흐름",
        "window_days": 30,
        "window_label": "최근 1개월",
        "comparison_label": "직전 1개월 대비",
        "volume_multiplier": 5.8,
    },
    {
        "id": "quarter",
        "label": "3개월",
        "title": "세 달간 주요 흐름",
        "window_days": 90,
        "window_label": "최근 3개월",
        "comparison_label": "직전 3개월 대비",
        "volume_multiplier": 11.5,
    },
]

HOME_TREND_POSITIONS = [
    (0.13, 0.18),
    (0.67, 0.22),
    (0.38, 0.42),
    (0.82, 0.53),
    (0.20, 0.68),
    (0.57, 0.76),
    (0.88, 0.78),
    (0.44, 0.15),
]


CATEGORIES = [
    {"id": "politics", "name": "정치", "color": "#8FA8C9"},
    {"id": "economy", "name": "경제", "color": "#D0A86C"},
    {"id": "society", "name": "사회", "color": "#91B7A2"},
    {"id": "culture", "name": "문화", "color": "#B7A0C9"},
    {"id": "world", "name": "국제", "color": "#7EA6B8"},
    {"id": "local", "name": "지역", "color": "#B3A17F"},
    {"id": "sports", "name": "스포츠", "color": "#C58F83"},
    {"id": "tech_science", "name": "IT·과학", "color": "#8799CC"},
]
CATEGORY_BY_ID = {category["id"]: category for category in CATEGORIES}


CATEGORY_KEYWORDS: dict[str, dict[str, int]] = {
    "politics": {
        "대통령": 5,
        "청와대": 5,
        "대통령실": 5,
        "국회": 5,
        "민주당": 5,
        "국민의힘": 5,
        "국힘": 5,
        "여당": 4,
        "야당": 4,
        "국회의원": 5,
        "정치": 4,
        "장동혁": 5,
        "한동훈": 5,
        "이재명": 4,
        "오세훈": 4,
        "홍준표": 4,
        "김민석": 4,
        "정부": 2,
        "정책": 2,
    },
    "economy": {
        "경제": 4,
        "금리": 5,
        "증시": 5,
        "주가": 5,
        "주주": 4,
        "부동산": 5,
        "아파트": 4,
        "집값": 4,
        "관세": 5,
        "무역": 5,
        "수출": 5,
        "수입": 3,
        "실적": 3,
        "투자": 3,
        "금융": 5,
        "은행": 4,
        "시장": 2,
        "산업": 3,
        "기업": 3,
        "비트코인": 6,
        "암호화폐": 6,
        "가상자산": 6,
        "이더리움": 6,
        "리플": 5,
        "xrp": 5,
        "솔라나": 5,
        "etf": 5,
        "달러": 4,
        "주택공급": 4,
        "재건축": 4,
        "코픽스": 6,
        "주담대": 5,
        "성과급": 4,
        "현대차": 4,
        "메모리": 4,
        "유가": 5,
        "기름값": 4,
        "매출": 4,
        "기업가치": 4,
        "ipo": 5,
        "자영업": 4,
        "주택": 4,
    },
    "society": {
        "경찰": 5,
        "법원": 4,
        "사건": 4,
        "사고": 4,
        "실종": 5,
        "수사": 5,
        "체포": 5,
        "범죄": 5,
        "노동": 5,
        "직장": 3,
        "교육": 4,
        "학교": 4,
        "병원": 4,
        "건강": 4,
        "당뇨": 5,
        "폭염": 4,
        "호우": 5,
        "태풍": 4,
        "날씨": 4,
        "재난": 5,
        "사망": 3,
        "집회": 4,
        "기후": 3,
        "주거": 3,
        "오물": 5,
        "살해": 5,
        "성관계": 4,
        "범칙금": 4,
        "수영장": 3,
        "근육": 3,
        "병사": 4,
        "파업": 4,
        "장례": 3,
        "마운자로": 5,
        "소나기": 4,
        "퇴사": 4,
    },
    "culture": {
        "연예": 5,
        "배우": 5,
        "가수": 5,
        "방송": 4,
        "예능": 5,
        "영화": 5,
        "드라마": 5,
        "공연": 5,
        "전시": 5,
        "문화": 4,
        "유재석": 6,
        "김수현": 6,
        "백지영": 6,
        "지예은": 6,
        "박신혜": 6,
        "미우새": 6,
        "놀면 뭐하니": 6,
        "미스코리아": 5,
        "크리에이터": 4,
        "웹툰": 5,
        "운세": 5,
        "전참시": 6,
        "도경완": 6,
        "다영": 5,
        "봉은사": 4,
        "스님": 4,
        "무화과": 4,
    },
    "world": {
        "미국": 4,
        "트럼프": 6,
        "러시아": 5,
        "우크라": 6,
        "이란": 6,
        "이스라엘": 6,
        "일본": 4,
        "중국": 4,
        "북한": 6,
        "북미": 5,
        "캐나다": 5,
        "하와이": 5,
        "파나마": 5,
        "튀르키예": 5,
        "중동": 5,
        "유엔": 5,
        "호르무즈": 6,
        "팔레스타인": 6,
        "소말리아": 5,
        "해적": 3,
        "해외": 3,
        "美": 5,
        "日": 5,
        "中": 5,
        "北": 5,
        "페루": 5,
        "세우타": 5,
        "다카이치": 5,
        "파리": 4,
        "공대공미사일": 6,
        "미사일": 4,
    },
    "local": {
        "서울시": 6,
        "제주": 5,
        "부산": 5,
        "대구": 5,
        "광주": 4,
        "수원": 5,
        "경남": 5,
        "경북": 5,
        "전남": 5,
        "전북": 4,
        "강원": 5,
        "충북": 5,
        "충남": 5,
        "거제": 6,
        "통영": 6,
        "김해시": 6,
        "파주시": 6,
        "순천": 5,
        "지역": 3,
        "지자체": 5,
        "특별재난지역": 5,
    },
    "sports": {
        "프로야구": 7,
        "프로축구": 7,
        "k리그": 7,
        "야구": 5,
        "축구": 5,
        "배드민턴": 6,
        "안세영": 7,
        "이강인": 7,
        "월드컵": 6,
        "올림픽": 6,
        "육상": 5,
        "배구": 5,
        "선수": 4,
        "감독": 3,
        "결승": 3,
        "우승": 3,
        "삼성라이온즈": 7,
        "한화-lg": 7,
        "현대가 더비": 7,
        "최형우": 7,
        "양현종": 7,
        "김경문": 6,
        "이범호": 6,
        "전북현대": 7,
        "울산": 4,
        "kia": 6,
        "nc": 5,
        "kt": 5,
        "타점": 5,
        "세이브": 5,
    },
    "tech_science": {
        "인공지능": 6,
        "ai": 5,
        "로봇": 6,
        "반도체": 5,
        "엔비디아": 6,
        "sk하이닉스": 6,
        "gpu": 5,
        "npu": 5,
        "스마트폰": 5,
        "배터리": 4,
        "드론": 5,
        "오픈ai": 6,
        "gpt": 5,
        "코덱스": 5,
        "앤트로픽": 6,
        "클로드": 5,
        "애플": 4,
        "안드로이드": 5,
        "소프트웨어": 5,
        "게임": 4,
        "그래픽 카드": 5,
        "스팀": 4,
        "테크": 3,
        "모델": 2,
        "칩": 4,
        "우주": 5,
        "코딩": 5,
        "dlss": 5,
        "모던 워페어": 6,
        "카르다노": 4,
        "arc raiders": 6,
        "월드 거래소": 5,
    },
}


NODE_DEFINITIONS: list[dict[str, Any]] = [
    # 정치
    {"id": "entity:lee-jae-myung", "label": "이재명", "type": "person", "category_id": "politics", "aliases": ["이재명", "이 대통령"]},
    {"id": "entity:presidential-office", "label": "대통령실", "type": "organization", "category_id": "politics", "aliases": ["대통령실", "청와대"]},
    {"id": "entity:national-assembly", "label": "국회", "type": "organization", "category_id": "politics", "aliases": ["국회", "국회의원"]},
    {"id": "entity:democratic-party", "label": "더불어민주당", "type": "organization", "category_id": "politics", "aliases": ["민주당", "더불어민주당", "여당"]},
    {"id": "entity:people-power-party", "label": "국민의힘", "type": "organization", "category_id": "politics", "aliases": ["국민의힘", "국힘", "야당"]},
    {"id": "entity:han-dong-hoon", "label": "한동훈", "type": "person", "category_id": "politics", "aliases": ["한동훈"]},
    {"id": "entity:oh-se-hoon", "label": "오세훈", "type": "person", "category_id": "politics", "aliases": ["오세훈"]},
    {"id": "topic:judiciary", "label": "사법부", "type": "topic", "category_id": "politics", "aliases": ["사법부", "대법관", "헌법", "재판"]},
    # 경제
    {"id": "topic:semiconductor-industry", "label": "반도체 산업", "type": "industry", "category_id": "economy", "aliases": ["반도체", "dram", "hbm"]},
    {"id": "entity:samsung-electronics", "label": "삼성전자", "type": "organization", "category_id": "economy", "aliases": ["삼성전자"]},
    {"id": "entity:sk-hynix", "label": "SK하이닉스", "type": "organization", "category_id": "economy", "aliases": ["sk하이닉스", "하이닉스"]},
    {"id": "topic:hbm", "label": "HBM", "type": "technology", "category_id": "economy", "aliases": ["hbm", "고대역폭메모리"]},
    {"id": "topic:real-estate", "label": "부동산", "type": "topic", "category_id": "economy", "aliases": ["부동산", "아파트", "집값", "주택공급", "재건축"]},
    {"id": "topic:interest-rate", "label": "기준금리", "type": "topic", "category_id": "economy", "aliases": ["기준금리", "금리"]},
    {"id": "topic:trade-tariff", "label": "관세·무역", "type": "topic", "category_id": "economy", "aliases": ["관세", "무역", "수출", "수입"]},
    {"id": "topic:financial-market", "label": "금융시장", "type": "topic", "category_id": "economy", "aliases": ["금융", "증시", "주가", "은행"]},
    {"id": "topic:crypto", "label": "가상자산", "type": "topic", "category_id": "economy", "aliases": ["가상자산", "암호화폐", "비트코인", "이더리움", "xrp", "솔라나"]},
    {"id": "topic:logistics", "label": "물류", "type": "industry", "category_id": "economy", "aliases": ["물류", "운하", "항로", "컨테이너선"]},
    # 사회
    {"id": "entity:police", "label": "경찰", "type": "organization", "category_id": "society", "aliases": ["경찰", "수사", "체포"]},
    {"id": "topic:missing-person", "label": "실종 사건", "type": "event", "category_id": "society", "aliases": ["실종"]},
    {"id": "topic:disaster-safety", "label": "재난 안전", "type": "topic", "category_id": "society", "aliases": ["재난", "사고", "대피", "안전"]},
    {"id": "topic:weather-climate", "label": "기후·날씨", "type": "topic", "category_id": "society", "aliases": ["날씨", "폭염", "호우", "태풍", "무더위", "소나기"]},
    {"id": "topic:labor", "label": "노동", "type": "topic", "category_id": "society", "aliases": ["노동", "직장", "근로"]},
    {"id": "topic:health", "label": "보건·건강", "type": "topic", "category_id": "society", "aliases": ["건강", "병원", "당뇨", "질병"]},
    {"id": "topic:education", "label": "교육", "type": "topic", "category_id": "society", "aliases": ["교육", "학교", "교사"]},
    {"id": "topic:housing-policy", "label": "주거 정책", "type": "policy", "category_id": "society", "aliases": ["주거", "주택공급", "대피생활"]},
    # 문화
    {"id": "topic:broadcast-entertainment", "label": "방송·예능", "type": "topic", "category_id": "culture", "aliases": ["방송", "예능", "미우새", "놀면 뭐하니"]},
    {"id": "topic:film-drama", "label": "영화·드라마", "type": "topic", "category_id": "culture", "aliases": ["영화", "드라마", "배우"]},
    {"id": "topic:music", "label": "음악", "type": "topic", "category_id": "culture", "aliases": ["음악", "가수", "콘서트", "k-pop"]},
    {"id": "topic:performance", "label": "공연", "type": "topic", "category_id": "culture", "aliases": ["공연", "무대", "연극"]},
    {"id": "topic:exhibition", "label": "전시·미술", "type": "topic", "category_id": "culture", "aliases": ["전시", "미술", "미술관"]},
    {"id": "topic:publishing", "label": "출판", "type": "topic", "category_id": "culture", "aliases": ["출판", "책", "작가"]},
    {"id": "topic:creator", "label": "크리에이터", "type": "topic", "category_id": "culture", "aliases": ["크리에이터", "유튜브", "sns"]},
    {"id": "topic:cultural-heritage", "label": "문화유산", "type": "topic", "category_id": "culture", "aliases": ["문화유산", "유산", "박물관"]},
    # 국제
    {"id": "entity:donald-trump", "label": "도널드 트럼프", "type": "person", "category_id": "world", "aliases": ["트럼프"]},
    {"id": "entity:united-states", "label": "미국", "type": "country", "category_id": "world", "aliases": ["미국", "미군", "미 해군", "연방법원", "백악관"]},
    {"id": "entity:north-korea", "label": "북한", "type": "country", "category_id": "world", "aliases": ["북한", "북한군", "김정은", "평양"]},
    {"id": "entity:china", "label": "중국", "type": "country", "category_id": "world", "aliases": ["중국", "베이징"]},
    {"id": "entity:japan", "label": "일본", "type": "country", "category_id": "world", "aliases": ["일본", "도쿄", "오키나와"]},
    {"id": "entity:iran", "label": "이란", "type": "country", "category_id": "world", "aliases": ["이란"]},
    {"id": "entity:israel", "label": "이스라엘", "type": "country", "category_id": "world", "aliases": ["이스라엘", "네타냐후"]},
    {"id": "entity:ukraine", "label": "우크라이나", "type": "country", "category_id": "world", "aliases": ["우크라이나", "우크라", "키이우"]},
    {"id": "entity:russia", "label": "러시아", "type": "country", "category_id": "world", "aliases": ["러시아", "러 ", "모스크바"]},
    {"id": "topic:strait-of-hormuz", "label": "호르무즈 해협", "type": "place", "category_id": "world", "aliases": ["호르무즈"]},
    {"id": "topic:nuclear-security", "label": "핵안보", "type": "topic", "category_id": "world", "aliases": ["핵추진", "핵무기", "핵안보", "탄도미사일"]},
    {"id": "entity:defense-ministry", "label": "국방부", "type": "organization", "category_id": "world", "aliases": ["국방부", "방위비", "미사일"]},
    # 지역
    {"id": "place:seoul", "label": "서울", "type": "place", "category_id": "local", "aliases": ["서울", "용산"]},
    {"id": "place:jeju", "label": "제주", "type": "place", "category_id": "local", "aliases": ["제주", "서귀포"]},
    {"id": "place:busan", "label": "부산", "type": "place", "category_id": "local", "aliases": ["부산", "부산항"]},
    {"id": "place:daegu", "label": "대구", "type": "place", "category_id": "local", "aliases": ["대구"]},
    {"id": "place:gyeongnam", "label": "경남", "type": "place", "category_id": "local", "aliases": ["경남", "거제", "통영", "김해"]},
    {"id": "place:gyeonggi", "label": "경기", "type": "place", "category_id": "local", "aliases": ["경기도", "수원", "광교", "파주"]},
    {"id": "place:jeonnam", "label": "전남", "type": "place", "category_id": "local", "aliases": ["전남", "순천"]},
    {"id": "place:gangwon", "label": "강원", "type": "place", "category_id": "local", "aliases": ["강원", "강릉"]},
    {"id": "topic:regional-transport", "label": "지역 교통", "type": "topic", "category_id": "local", "aliases": ["지역 교통", "도시철도", "버스", "도로 통제"]},
    {"id": "topic:regional-economy", "label": "지역 경제", "type": "topic", "category_id": "local", "aliases": ["지역 경제", "지역 상권", "관광"]},
    # 스포츠
    {"id": "entity:an-se-young", "label": "안세영", "type": "person", "category_id": "sports", "aliases": ["안세영"]},
    {"id": "entity:lee-kang-in", "label": "이강인", "type": "person", "category_id": "sports", "aliases": ["이강인"]},
    {"id": "topic:professional-baseball", "label": "프로야구", "type": "sport", "category_id": "sports", "aliases": ["프로야구", "야구", "삼성라이온즈", "한화-lg", "kia"]},
    {"id": "topic:k-league", "label": "K리그", "type": "sport", "category_id": "sports", "aliases": ["k리그", "프로축구", "현대가 더비", "전북현대"]},
    {"id": "topic:badminton", "label": "배드민턴", "type": "sport", "category_id": "sports", "aliases": ["배드민턴", "셔틀콕"]},
    {"id": "topic:football", "label": "축구", "type": "sport", "category_id": "sports", "aliases": ["축구", "월드컵", "아틀레티코"]},
    {"id": "topic:volleyball", "label": "배구", "type": "sport", "category_id": "sports", "aliases": ["배구", "김연경", "양효진"]},
    {"id": "topic:athletics", "label": "육상", "type": "sport", "category_id": "sports", "aliases": ["육상", "마스터즈", "10k"]},
    # IT·과학
    {"id": "topic:artificial-intelligence", "label": "인공지능", "type": "technology", "category_id": "tech_science", "aliases": ["인공지능", "ai ", "ai·", "ai 모델"]},
    {"id": "entity:openai", "label": "OpenAI", "type": "organization", "category_id": "tech_science", "aliases": ["오픈ai", "openai", "gpt", "코덱스"]},
    {"id": "entity:nvidia", "label": "NVIDIA", "type": "organization", "category_id": "tech_science", "aliases": ["엔비디아", "nvidia"]},
    {"id": "entity:anthropic", "label": "Anthropic", "type": "organization", "category_id": "tech_science", "aliases": ["앤트로픽", "클로드"]},
    {"id": "entity:apple", "label": "Apple", "type": "organization", "category_id": "tech_science", "aliases": ["애플", "비전 프로"]},
    {"id": "topic:robotics", "label": "로봇", "type": "technology", "category_id": "tech_science", "aliases": ["로봇", "휴머노이드"]},
    {"id": "topic:drones", "label": "드론", "type": "technology", "category_id": "tech_science", "aliases": ["드론"]},
    {"id": "topic:ai-chip", "label": "AI 반도체", "type": "technology", "category_id": "tech_science", "aliases": ["npu", "ai 칩", "자체 칩"]},
    {"id": "topic:smart-device", "label": "스마트 기기", "type": "technology", "category_id": "tech_science", "aliases": ["스마트폰", "스마트 안경", "스마트워치", "레드미 워치"]},
    {"id": "topic:gaming", "label": "게임", "type": "topic", "category_id": "tech_science", "aliases": ["게임", "스팀", "call of duty", "arc raiders"]},
    {"id": "topic:gpu", "label": "GPU", "type": "technology", "category_id": "tech_science", "aliases": ["gpu", "그래픽 카드", "rtx"]},
]
NODE_BY_ID = {node["id"]: node for node in NODE_DEFINITIONS}


SYNTHETIC_CURRENT_TEMPLATES: dict[str, list[tuple[str, str, list[str]]]] = {
    "politics": [
        ("국회, 민생 법안 처리 일정 조율", "여야가 주요 민생 법안의 심사 일정과 쟁점을 조율하고 있습니다.", ["entity:national-assembly"]),
        ("대통령실, 산업 전환 정책 점검 회의", "산업 전환 정책의 진행 상황과 후속 과제를 점검했습니다.", ["entity:presidential-office"]),
        ("여야, 사법 제도 개선안 두고 논의", "사법 제도 개선 방향을 두고 여야의 논의가 이어졌습니다.", ["topic:judiciary", "entity:national-assembly"]),
        ("지방 현안 협의체 출범…국회와 지자체 참여", "지역 현안을 논의하는 협의체가 첫 회의를 열었습니다.", ["entity:national-assembly"]),
    ],
    "economy": [
        ("반도체 공급망 투자, 하반기 계획 구체화", "반도체 기업들이 공급망 안정과 생산 효율을 위한 투자 계획을 구체화했습니다.", ["topic:semiconductor-industry", "topic:hbm", "entity:sk-hynix", "entity:nvidia"]),
        ("기준금리 전망 엇갈려…시장 변동성 주시", "금리 경로를 둘러싼 전망이 엇갈리며 금융시장이 주요 지표를 주시하고 있습니다.", ["topic:interest-rate", "topic:financial-market"]),
        ("항만 물류 디지털 전환 사업 확대", "항만 운영과 화물 추적을 잇는 디지털 물류 사업이 확대됩니다.", ["topic:logistics", "place:busan"]),
        ("수출 기업, 관세 변화 대응책 마련", "수출 기업들이 관세와 통상 환경 변화에 대응할 방안을 마련하고 있습니다.", ["topic:trade-tariff"]),
    ],
    "society": [
        ("폭염 장기화에 취약계층 지원 강화", "지자체와 관계 기관이 폭염 취약계층 지원과 현장 점검을 강화했습니다.", ["topic:weather-climate", "topic:disaster-safety"]),
        ("지역 응급의료 연계체계 합동 점검", "의료기관과 소방 당국이 응급환자 이송 체계를 함께 점검했습니다.", ["topic:health", "topic:disaster-safety"]),
        ("직장 내 괴롭힘 예방 지침 개정 논의", "노동 현장의 신고와 보호 절차를 보완하는 논의가 진행됐습니다.", ["topic:labor"]),
        ("학교 안전교육, 체험형 과정으로 확대", "학교 현장에서 재난 대응을 익히는 체험형 교육이 확대됩니다.", ["topic:education", "topic:disaster-safety"]),
    ],
    "culture": [
        ("독립영화 기획전, 지역 극장서 잇따라 개막", "신진 감독의 작품을 소개하는 독립영화 기획전이 지역 극장에서 열립니다.", ["topic:film-drama"]),
        ("국립미술관, 디지털 아카이브 전시 공개", "소장 자료와 현대 기술을 결합한 디지털 아카이브 전시가 공개됐습니다.", ["topic:exhibition", "topic:cultural-heritage"]),
        ("도심 야외무대서 여름 음악축제 개최", "다양한 장르의 음악가가 참여하는 야외 음악축제가 열립니다.", ["topic:music", "topic:performance"]),
        ("출판계, 짧은 읽기와 오디오북 독자 확대", "출판사들이 달라진 독서 습관에 맞춘 콘텐츠를 선보이고 있습니다.", ["topic:publishing"]),
        ("지역 문화유산 야간 개방 프로그램 확대", "지역 문화유산을 새롭게 경험할 수 있는 야간 프로그램이 확대됩니다.", ["topic:cultural-heritage"]),
        ("신진 창작자 지원 플랫폼 참여작 공개", "신진 창작자의 제작과 유통을 돕는 지원 프로그램의 참여작이 공개됐습니다.", ["topic:creator"]),
        ("소극장 연극제 개막…관객과의 대화 마련", "다양한 창작극과 관객 참여 프로그램을 만날 수 있는 연극제가 개막했습니다.", ["topic:performance"]),
        ("방송사, 공익 다큐멘터리 공동 제작", "지역과 환경을 기록하는 공익 다큐멘터리 제작이 시작됐습니다.", ["topic:broadcast-entertainment"]),
        ("웹툰 원작 드라마, 해외 공개 일정 확정", "웹툰을 원작으로 한 드라마의 해외 공개 일정이 확정됐습니다.", ["topic:film-drama", "topic:creator"]),
        ("박물관 교육 프로그램, 청소년 참여 확대", "전시와 체험을 연결한 청소년 교육 프로그램이 확대됩니다.", ["topic:cultural-heritage"]),
    ],
    "world": [
        ("미국·중국, 공급망 실무 협의 재개", "양국이 공급망과 통상 현안을 다루는 실무 협의를 재개했습니다.", ["entity:united-states", "entity:china"]),
        ("국제사회, 중동 항행 안전 공동 대응 논의", "주요국이 중동 해역의 항행 안전을 위한 공동 대응을 논의했습니다.", ["topic:strait-of-hormuz"]),
        ("일본, 재난 대응 예산 확대 검토", "일본 정부가 대형 재난에 대비한 대응 예산 확대를 검토하고 있습니다.", ["entity:japan"]),
        ("우크라이나 평화 협상 조건 놓고 공방", "전쟁 종식 조건과 안전 보장을 둘러싼 국제사회의 논의가 이어졌습니다.", ["entity:ukraine", "entity:russia"]),
    ],
    "local": [
        ("부산항, 친환경 물류 전환 실증 확대", "부산항이 친환경 장비와 디지털 화물 관리 실증을 확대합니다.", ["place:busan", "topic:logistics"]),
        ("제주, 해상 안전 대응체계 합동 점검", "제주 지역 관계 기관이 여름철 해상 사고 대응체계를 점검했습니다.", ["place:jeju", "topic:disaster-safety"]),
        ("대구, 도심 폭염 쉼터 운영 확대", "대구시가 폭염 취약 시간대에 맞춰 도심 쉼터 운영을 확대했습니다.", ["place:daegu", "topic:weather-climate"]),
        ("경남 수해지역 복구 지원 장기화", "경남 수해지역의 생활 기반 복구와 주민 지원이 이어지고 있습니다.", ["place:gyeongnam", "topic:disaster-safety"]),
        ("전남, 지역 의료 접근성 개선 사업 추진", "전남이 의료 취약지역의 이동 진료와 연계 진료를 확대합니다.", ["place:jeonnam", "topic:health"]),
        ("서울, 심야 대중교통 노선 조정", "서울시가 이용량 변화를 반영해 심야 대중교통 노선을 조정합니다.", ["place:seoul", "topic:regional-transport"]),
        ("경기 남부 반도체 교통망 확충 논의", "산업단지 통근과 물류를 지원하는 교통망 확충 논의가 진행됐습니다.", ["place:gyeonggi", "topic:semiconductor-industry", "topic:regional-transport"]),
        ("강원 관광지, 대중교통 연계 서비스 확대", "주요 관광지와 터미널을 잇는 대중교통 연계 서비스가 확대됩니다.", ["place:gangwon", "topic:regional-economy"]),
        ("지역 상권 공동배송 실증 시작", "소상공인의 물류비를 낮추기 위한 공동배송 실증 사업이 시작됐습니다.", ["topic:regional-economy", "topic:logistics"]),
        ("부산·경남 광역교통 협의 재개", "부산과 경남을 잇는 광역교통 개선안 논의가 재개됐습니다.", ["place:busan", "place:gyeongnam", "topic:regional-transport"]),
        ("제주 농산물 유통망 개선 시범사업", "산지와 소비지를 잇는 농산물 공동 물류 시범사업이 추진됩니다.", ["place:jeju", "topic:regional-economy", "topic:logistics"]),
        ("대구 문화시설 야간 개방 확대", "대구의 주요 문화시설이 여름철 야간 개방 프로그램을 확대합니다.", ["place:daegu", "topic:cultural-heritage"]),
    ],
    "sports": [
        ("여자배구 대표팀, 국제대회 대비 전술 훈련", "대표팀이 국제대회를 앞두고 조직력과 수비 전술을 점검했습니다.", ["topic:volleyball"]),
        ("프로야구 순위 경쟁 치열…불펜 운용 변수", "상위권 팀들의 접전이 이어지며 후반기 불펜 운용이 변수로 떠올랐습니다.", ["topic:professional-baseball"]),
        ("K리그, 여름 이적시장 이후 판도 변화", "주요 구단의 전력 보강이 후반기 순위 경쟁에 영향을 주고 있습니다.", ["topic:k-league"]),
        ("배드민턴 대표팀, 세계대회 앞두고 컨디션 점검", "대표팀 선수들이 세계대회를 앞두고 마지막 실전 점검에 나섰습니다.", ["topic:badminton"]),
        ("육상 유망주, 개인 최고기록 잇따라 경신", "국내 육상 유망주들이 주요 종목에서 개인 최고기록을 경신했습니다.", ["topic:athletics"]),
        ("축구대표팀, 새 전술 실험 본격화", "대표팀이 다음 국제경기를 준비하며 새로운 전술 조합을 시험했습니다.", ["topic:football"]),
        ("프로배구 새 시즌 일정 발표", "프로배구 새 시즌의 주요 일정과 운영 계획이 발표됐습니다.", ["topic:volleyball"]),
        ("생활체육 대회, 지역 참가자 규모 확대", "지역 생활체육 대회의 종목과 참가 규모가 확대됐습니다.", ["topic:athletics"]),
    ],
    "tech_science": [
        ("국내 AI 반도체 실증 사업 확대", "국산 AI 반도체의 데이터센터 적용을 검증하는 실증 사업이 확대됩니다.", ["topic:artificial-intelligence", "topic:ai-chip"]),
        ("휴머노이드 로봇, 물류 현장 시험 투입", "휴머노이드 로봇이 반복 작업을 지원하기 위해 물류 현장에 시험 투입됩니다.", ["topic:robotics", "topic:logistics"]),
        ("생성형 AI 서비스, 출처 표시 기능 강화", "생성형 AI 서비스가 답변의 근거와 출처를 보여주는 기능을 강화했습니다.", ["topic:artificial-intelligence"]),
        ("스마트 기기 배터리 효율 개선 경쟁", "모바일 기기 제조사들이 배터리 효율과 수명을 높이는 기술을 선보였습니다.", ["topic:smart-device"]),
    ],
}

REQUIRED_NODE_SUPPORT = {
    "topic:hbm": (
        "economy",
        "HBM 공급망, AI 반도체 투자와 맞물려 확대",
        "고대역폭메모리 공급망과 AI 반도체 투자의 연결을 설명하는 시연용 기사입니다.",
        ["topic:hbm", "topic:semiconductor-industry", "entity:sk-hynix", "entity:nvidia"],
    ),
}


CURATED_EDGES = [
    ("entity:north-korea", "entity:defense-ministry", "안보 이슈"),
    ("entity:defense-ministry", "topic:nuclear-security", "국방 정책"),
    ("topic:nuclear-security", "entity:china", "동북아 안보"),
    ("topic:nuclear-security", "entity:united-states", "동맹 안보"),
    ("entity:north-korea", "topic:drones", "군사 기술"),
    ("entity:iran", "topic:strait-of-hormuz", "중동 항행"),
    ("topic:strait-of-hormuz", "entity:united-states", "해양 안보"),
    ("entity:united-states", "entity:donald-trump", "미국 정치"),
    ("entity:donald-trump", "topic:trade-tariff", "통상 정책"),
    ("topic:semiconductor-industry", "entity:sk-hynix", "산업 참여"),
    ("topic:semiconductor-industry", "entity:samsung-electronics", "산업 참여"),
    ("topic:semiconductor-industry", "topic:hbm", "핵심 기술"),
    ("topic:hbm", "entity:sk-hynix", "생산 기업"),
    ("topic:hbm", "entity:nvidia", "AI 공급망"),
    ("entity:nvidia", "topic:gpu", "제품 생태계"),
    ("topic:gpu", "topic:artificial-intelligence", "컴퓨팅 기반"),
    ("topic:artificial-intelligence", "entity:openai", "AI 서비스"),
    ("topic:artificial-intelligence", "entity:anthropic", "AI 서비스"),
    ("topic:artificial-intelligence", "topic:ai-chip", "컴퓨팅 인프라"),
    ("topic:logistics", "place:busan", "항만 물류"),
    ("topic:logistics", "topic:trade-tariff", "수출입 연결"),
    ("topic:weather-climate", "topic:disaster-safety", "재난 대응"),
    ("topic:disaster-safety", "place:gyeongnam", "지역 대응"),
    ("topic:disaster-safety", "place:jeju", "지역 대응"),
    ("topic:broadcast-entertainment", "topic:film-drama", "콘텐츠 산업"),
    ("topic:film-drama", "topic:creator", "원천 콘텐츠"),
    ("topic:performance", "topic:music", "공연 콘텐츠"),
    ("topic:k-league", "topic:football", "국내 축구"),
    ("entity:lee-kang-in", "topic:football", "선수"),
    ("entity:an-se-young", "topic:badminton", "선수"),
]


USER_HISTORY_COUNTS = {
    "economy": 30,
    "tech_science": 28,
    "world": 18,
    "society": 12,
    "politics": 8,
    "local": 5,
    "culture": 3,
    "sports": 0,
}
USER_CURRENT_READ_COUNTS = {
    "economy": 8,
    "tech_science": 6,
    "world": 4,
    "society": 3,
    "politics": 2,
    "local": 1,
}
USER_INTERESTS = {
    "economy": 0.92,
    "tech_science": 0.88,
    "world": 0.67,
    "society": 0.52,
    "politics": 0.46,
    "local": 0.35,
    "culture": 0.28,
    "sports": 0.0,
}


# [Text helpers]

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "").lower()).strip()


def normalized_title(value: str | None) -> str:
    text = normalize_text(value)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def find_gnews_bucket(label: str) -> str:
    for bucket in ("world", "business", "technology", "entertainment", "nation", "general"):
        if bucket in label:
            return bucket
    return "unknown"


def term_count(text: str, term: str) -> int:
    """영문 약어가 다른 단어 내부에서 오탐되지 않도록 등장 횟수를 센다."""
    normalized_term = normalize_text(term)
    if re.fullmatch(r"[a-z0-9][a-z0-9+._-]*", normalized_term):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
        return len(re.findall(pattern, text))
    return text.count(normalized_term)


# [Classification]

def classify_article(article: dict[str, Any]) -> dict[str, Any]:
    title = normalize_text(article.get("title"))
    description = normalize_text(article.get("description"))
    scores = {category["id"]: 0 for category in CATEGORIES}
    matched: dict[str, list[str]] = defaultdict(list)

    for category_id, keywords in CATEGORY_KEYWORDS.items():
        for term, weight in keywords.items():
            title_hits = term_count(title, term)
            description_hits = term_count(description, term)
            if title_hits or description_hits:
                scores[category_id] += weight * min(title_hits, 2)
                scores[category_id] += max(1, weight // 2) * min(description_hits, 2)
                matched[category_id].append(term)

    ranked = sorted(
        scores.items(),
        key=lambda item: (item[1], -list(CATEGORY_BY_ID).index(item[0])),
        reverse=True,
    )
    primary_category_id, best_score = ranked[0]
    if best_score == 0:
        # 정보가 거의 없는 placeholder도 스키마상 대표 카테고리는 필요하다.
        # 실제 화면에서는 quality flag로 제외하고 review queue에서 확인한다.
        primary_category_id = "society"
    margin = best_score - ranked[1][1] if best_score else 0
    secondary_threshold = max(4, math.ceil(best_score * 0.45))
    category_ids = [
        category_id
        for category_id, score in ranked
        if score >= secondary_threshold
    ]
    if primary_category_id not in category_ids:
        category_ids.insert(0, primary_category_id)
    category_ids = category_ids[:4]

    if best_score >= 8:
        confidence = "high"
    elif best_score >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "primary_category_id": primary_category_id,
        "primary_category_name": CATEGORY_BY_ID[primary_category_id]["name"],
        "category_ids": category_ids,
        "category_names": [CATEGORY_BY_ID[category_id]["name"] for category_id in category_ids],
        "classification": {
            "method": "service_taxonomy_keyword_multilabel",
            "confidence": confidence,
            "score": best_score,
            "margin": margin,
            "matched_terms": {
                category_id: sorted(set(matched.get(category_id, [])))
                for category_id in category_ids
            },
            "gnews_bucket_observed_only": find_gnews_bucket(
                article.get("first_request_label") or ""
            ),
            "gnews_bucket_used_for_classification": False,
            "provisional": True,
        },
    }


def node_ids_for_text(article: dict[str, Any]) -> list[str]:
    text = normalize_text(
        " ".join(
            [
                article.get("title") or "",
                article.get("description") or "",
                article.get("content") or "",
            ]
        )
    )
    matches: list[tuple[int, str]] = []
    for node in NODE_DEFINITIONS:
        best_alias_length = max(
            (
                len(normalize_text(alias))
                for alias in node["aliases"]
                if normalize_text(alias) and term_count(text, alias)
            ),
            default=0,
        )
        if best_alias_length:
            matches.append((best_alias_length, node["id"]))

    matches.sort(key=lambda item: (-item[0], item[1]))
    result = [f"category:{category_id}" for category_id in article["category_ids"]]
    for _, node_id in matches:
        if node_id not in result:
            result.append(node_id)
        if len(result) >= 7:
            break
    return result


def quality_flags(articles: list[dict[str, Any]]) -> None:
    seen_titles: dict[str, str] = {}
    placeholders = {
        "kbs뉴스",
        "연합뉴스한민족센터",
        "사람과지역의가치를생각합니다",
        "오리엔탈나이트드림즈",
    }
    for article in sorted(articles, key=lambda item: item["published_at"]):
        flags: list[str] = []
        key = normalized_title(article.get("title"))
        if not key or len(key) < 8 or key in placeholders:
            flags.append("placeholder_or_low_information_title")
        if key in seen_titles:
            flags.append("duplicate_title")
            article["duplicate_of"] = seen_titles[key]
        else:
            seen_titles[key] = article["id"]
        if not article.get("description"):
            flags.append("missing_description")
        if not article.get("image"):
            flags.append("missing_image")
        article["quality_flags"] = flags
        article["mock_eligible"] = not any(
            flag in {"placeholder_or_low_information_title", "duplicate_title"}
            for flag in flags
        )


def normalize_real_articles(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for source in source_rows:
        classification = classify_article(source)
        article = {
            "id": f"article:gnews:{source['article_id']}",
            "data_role": "current",
            "synthetic": False,
            "provider": "gnews",
            "title": source.get("title"),
            "description": source.get("description"),
            "summary": source.get("description"),
            "content_preview": source.get("content"),
            "url": source.get("url"),
            "canonical_url": source.get("canonical_url"),
            "external_link_available": bool(source.get("url")),
            "image": source.get("image"),
            "image_kind": "publisher",
            "published_at": source.get("published_at"),
            "source": {
                "id": source.get("source_id"),
                "name": source.get("source_name"),
                "url": source.get("source_url"),
                "country": source.get("source_country"),
            },
            "primary_category_id": classification["primary_category_id"],
            "primary_category_name": classification["primary_category_name"],
            "category_ids": classification["category_ids"],
            "category_names": classification["category_names"],
            "classification": classification["classification"],
            "provenance": {
                "kind": "collected",
                "provider": "gnews",
                "original_article_id": source.get("article_id"),
                "request_label": source.get("first_request_label"),
                "raw_file": source.get("raw_file"),
            },
        }
        article["node_ids"] = node_ids_for_text(article)
        articles.append(article)
    quality_flags(articles)
    return articles


# [Synthetic supplements]

def make_synthetic_article(
    *,
    category_id: str,
    title: str,
    description: str,
    node_ids: list[str],
    published_at: datetime,
    sequence: int,
    data_role: str,
) -> dict[str, Any]:
    article_id = stable_id(
        "article:synthetic",
        f"{data_role}|{category_id}|{title}|{published_at.isoformat()}|{sequence}",
    )
    secondary_category_ids = [
        NODE_BY_ID[node_id]["category_id"]
        for node_id in node_ids
        if node_id in NODE_BY_ID and NODE_BY_ID[node_id]["category_id"] != category_id
    ]
    category_ids = list(dict.fromkeys([category_id, *secondary_category_ids]))[:4]
    all_nodes = [*(f"category:{item}" for item in category_ids), *node_ids]
    all_nodes = list(
        dict.fromkeys(
            node_id
            for node_id in all_nodes
            if node_id in NODE_BY_ID or node_id.startswith("category:")
        )
    )
    return {
        "id": article_id,
        "data_role": data_role,
        "synthetic": True,
        "provider": "starlight_mock_generator",
        "title": title,
        "description": description,
        "summary": description,
        "content_preview": description,
        "url": None,
        "canonical_url": None,
        "external_link_available": False,
        "image": None,
        "image_kind": "category_placeholder",
        "published_at": iso(published_at),
        "source": {
            "id": "source:starlight-demo",
            "name": "별빛 뉴스 시연 데이터",
            "url": None,
            "country": "kr",
        },
        "primary_category_id": category_id,
        "primary_category_name": CATEGORY_BY_ID[category_id]["name"],
        "category_ids": category_ids,
        "category_names": [CATEGORY_BY_ID[item]["name"] for item in category_ids],
        "classification": {
            "method": "assigned_by_mock_generator",
            "confidence": "high",
            "score": None,
            "margin": None,
            "matched_terms": [],
            "gnews_bucket_observed_only": None,
            "gnews_bucket_used_for_classification": False,
            "provisional": False,
        },
        "node_ids": all_nodes,
        "quality_flags": ["synthetic_mock_data", "missing_image", "no_external_link"],
        "mock_eligible": True,
        "provenance": {
            "kind": "generated",
            "generator": "scripts/build_mock_dataset.py",
            "purpose": data_role,
            "disclosure": "시연용 합성 데이터",
        },
    }


def supplement_current_articles(
    real_articles: list[dict[str, Any]], reference_at: datetime
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    eligible_counts = Counter(
        category_id
        for article in real_articles
        if article["mock_eligible"]
        for category_id in article["category_ids"]
    )
    supplements: list[dict[str, Any]] = []
    supplement_counts: dict[str, int] = {}
    for category in CATEGORIES:
        category_id = category["id"]
        deficit = max(0, MIN_CURRENT_ARTICLES_PER_CATEGORY - eligible_counts[category_id])
        supplement_counts[category_id] = deficit
        templates = SYNTHETIC_CURRENT_TEMPLATES[category_id]
        for index in range(deficit):
            title, description, node_ids = templates[index % len(templates)]
            cycle = index // len(templates)
            if cycle:
                title = f"{title}…후속 동향 {cycle + 1}"
            published_at = reference_at - timedelta(minutes=37 * (index + 3), hours=category_index(category_id))
            supplements.append(
                make_synthetic_article(
                    category_id=category_id,
                    title=title,
                    description=description,
                    node_ids=node_ids,
                    published_at=published_at,
                    sequence=index,
                    data_role="current_supplement",
                )
            )

    covered_nodes = {
        node_id
        for article in [*real_articles, *supplements]
        if article["mock_eligible"]
        for node_id in article["node_ids"]
    }
    for node_id, (category_id, title, description, node_ids) in REQUIRED_NODE_SUPPORT.items():
        if node_id in covered_nodes:
            continue
        supplements.append(
            make_synthetic_article(
                category_id=category_id,
                title=title,
                description=description,
                node_ids=node_ids,
                published_at=reference_at - timedelta(hours=5, minutes=17),
                sequence=1000 + len(supplements),
                data_role="current_supplement",
            )
        )
        supplement_counts[category_id] += 1
    return supplements, supplement_counts


def category_index(category_id: str) -> int:
    return next(index for index, category in enumerate(CATEGORIES) if category["id"] == category_id)


def history_subjects(category_id: str) -> list[tuple[str, list[str]]]:
    return [
        (re.sub(r"[.…].*$", "", title), node_ids)
        for title, _, node_ids in SYNTHETIC_CURRENT_TEMPLATES[category_id]
    ]


def build_history_articles(reference_at: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    articles: list[dict[str, Any]] = []
    read_events: list[dict[str, Any]] = []
    angles = ["배경과 쟁점", "후속 변화", "현장 반응", "숫자로 본 흐름", "정책 영향"]
    sequence = 0
    session_index = 0
    category_queue = [
        category_id
        for category_id, count in USER_HISTORY_COUNTS.items()
        for _ in range(count)
    ]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(category_queue)

    for sequence, category_id in enumerate(category_queue):
        if sequence % 3 == 0:
            session_index += 1
        session_start = reference_at - timedelta(days=89 - session_index * 2.45)
        session_start = session_start.replace(hour=7 + (session_index % 4) * 3, minute=0, second=0, microsecond=0)
        subject, node_ids = history_subjects(category_id)[sequence % len(history_subjects(category_id))]
        angle = angles[(sequence + category_index(category_id)) % len(angles)]
        title = f"{subject}, {angle}"
        description = f"{subject}와 관련된 변화, 주요 이해관계자와 다음 쟁점을 정리한 시연용 개인 기록입니다."
        published_at = session_start - timedelta(hours=2, minutes=sequence % 17)
        article = make_synthetic_article(
            category_id=category_id,
            title=title,
            description=description,
            node_ids=node_ids,
            published_at=published_at,
            sequence=sequence,
            data_role="personal_history",
        )
        articles.append(article)
        read_at = session_start + timedelta(minutes=18 * (sequence % 3))
        read_events.append(
            {
                "id": stable_id("event", f"history-read|{article['id']}"),
                "type": "article_read",
                "user_id": "user:demo-experienced",
                "session_id": f"session:history:{session_index:02d}",
                "occurred_at": iso(read_at),
                "article_id": article["id"],
                "primary_category_id": article["primary_category_id"],
                "category_ids": article["category_ids"],
                "node_ids": article["node_ids"],
                "synthetic": True,
            }
        )
    return articles, read_events


def select_current_reads(
    articles: list[dict[str, Any]], reference_at: datetime
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for article in articles:
        if (
            article["data_role"] == "current"
            and article["mock_eligible"]
            and parse_dt(article["published_at"]) <= reference_at
        ):
            by_category[article["primary_category_id"]].append(article)
    for values in by_category.values():
        values.sort(key=lambda item: item["published_at"], reverse=True)

    for category_id, count in USER_CURRENT_READ_COUNTS.items():
        selected.extend(by_category[category_id][:count])

    events: list[dict[str, Any]] = []
    for index, article in enumerate(selected):
        published_at = parse_dt(article["published_at"])
        read_at = max(published_at + timedelta(minutes=8), reference_at - timedelta(minutes=(len(selected) - index) * 11))
        events.append(
            {
                "id": stable_id("event", f"current-read|{article['id']}"),
                "type": "article_read",
                "user_id": "user:demo-experienced",
                "session_id": f"session:current:{index // 4 + 1:02d}",
                "occurred_at": iso(read_at),
                "article_id": article["id"],
                "primary_category_id": article["primary_category_id"],
                "category_ids": article["category_ids"],
                "node_ids": article["node_ids"],
                "synthetic": True,
            }
        )
    return events


# [Stories and graph]

def title_tokens(value: str) -> set[str]:
    stop = {"종합", "속보", "뉴스", "기자", "단독", "영상", "포토"}
    return {
        token
        for token in re.findall(r"[0-9a-z가-힣]{2,}", normalize_text(value))
        if token not in stop
    }


def build_stories(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = [article for article in articles if article["data_role"] != "personal_history"]
    parent = list(range(len(current)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    token_sets = [title_tokens(article["title"]) for article in current]
    for left, right in combinations(range(len(current)), 2):
        if current[left]["primary_category_id"] != current[right]["primary_category_id"]:
            continue
        union_size = len(token_sets[left] | token_sets[right])
        similarity = len(token_sets[left] & token_sets[right]) / union_size if union_size else 0
        if similarity >= 0.58:
            union(left, right)

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, article in enumerate(current):
        groups[find(index)].append(article)

    stories: list[dict[str, Any]] = []
    for group in groups.values():
        group.sort(key=lambda item: item["published_at"], reverse=True)
        story_id = stable_id("story", "|".join(sorted(item["id"] for item in group)))
        for article in group:
            article["story_id"] = story_id
        stories.append(
            {
                "id": story_id,
                "title": group[0]["title"],
                "primary_category_id": group[0]["primary_category_id"],
                "category_ids": sorted(
                    {
                        category_id
                        for article in group
                        for category_id in article["category_ids"]
                    }
                ),
                "article_ids": [article["id"] for article in group],
                "source_count": len({article["source"]["name"] for article in group}),
                "article_count": len(group),
                "synthetic_article_count": sum(article["synthetic"] for article in group),
                "latest_published_at": group[0]["published_at"],
            }
        )
    stories.sort(key=lambda item: item["latest_published_at"], reverse=True)
    return stories


def category_centers() -> dict[str, tuple[float, float]]:
    return {
        "politics": (0.27, 0.24),
        "economy": (0.48, 0.24),
        "society": (0.68, 0.30),
        "culture": (0.80, 0.52),
        "world": (0.66, 0.72),
        "local": (0.45, 0.75),
        "sports": (0.22, 0.66),
        "tech_science": (0.18, 0.43),
    }


def deterministic_point(node_id: str, category_id: str, ordinal: int) -> dict[str, float]:
    digest = int(hashlib.sha1(node_id.encode("utf-8")).hexdigest()[:8], 16)
    angle = (digest % 360) * math.pi / 180
    radius = 0.045 + (ordinal % 5) * 0.018
    center_x, center_y = category_centers()[category_id]
    return {
        "x": round(min(0.95, max(0.05, center_x + math.cos(angle) * radius)), 4),
        "y": round(min(0.95, max(0.05, center_y + math.sin(angle) * radius)), 4),
    }


def build_graph(
    articles: list[dict[str, Any]], read_events: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    article_ids_by_node: dict[str, list[str]] = defaultdict(list)
    current_article_ids_by_node: dict[str, list[str]] = defaultdict(list)
    read_count_by_node: Counter[str] = Counter()
    for article in articles:
        for node_id in article["node_ids"]:
            article_ids_by_node[node_id].append(article["id"])
            if article["data_role"] != "personal_history":
                current_article_ids_by_node[node_id].append(article["id"])
    for event in read_events:
        read_count_by_node.update(event["node_ids"])

    nodes: list[dict[str, Any]] = []
    for index, category in enumerate(CATEGORIES):
        category_id = category["id"]
        node_id = f"category:{category_id}"
        nodes.append(
            {
                "id": node_id,
                "label": category["name"],
                "type": "category",
                "category_id": category_id,
                "aliases": [category["name"]],
                "article_ids": article_ids_by_node[node_id],
                "current_article_ids": current_article_ids_by_node[node_id],
                "read_count": read_count_by_node[node_id],
                "layout": {"personal_map": {"x": category_centers()[category_id][0], "y": category_centers()[category_id][1]}},
                "synthetic": False,
            }
        )

    per_category_index: Counter[str] = Counter()
    for definition in NODE_DEFINITIONS:
        category_id = definition["category_id"]
        ordinal = per_category_index[category_id]
        per_category_index[category_id] += 1
        nodes.append(
            {
                **definition,
                "article_ids": article_ids_by_node[definition["id"]],
                "current_article_ids": current_article_ids_by_node[definition["id"]],
                "read_count": read_count_by_node[definition["id"]],
                "layout": {"personal_map": deterministic_point(definition["id"], category_id, ordinal)},
                "synthetic": False,
            }
        )

    edge_data: dict[tuple[str, str], dict[str, Any]] = {}

    def add_edge(
        source: str,
        target: str,
        relation: str,
        *,
        article_id: str | None = None,
        source_name: str | None = None,
        base_weight: int = 0,
    ) -> None:
        if source == target:
            return
        left, right = sorted((source, target))
        key = (left, right)
        item = edge_data.setdefault(
            key,
            {
                "id": stable_id("edge", f"{left}|{right}"),
                "source": left,
                "target": right,
                "relations": [],
                "article_ids": [],
                "source_names": [],
                "base_weight": 0,
            },
        )
        if relation not in item["relations"]:
            item["relations"].append(relation)
        if article_id and article_id not in item["article_ids"]:
            item["article_ids"].append(article_id)
        if source_name and source_name not in item["source_names"]:
            item["source_names"].append(source_name)
        item["base_weight"] += base_weight

    for definition in NODE_DEFINITIONS:
        add_edge(
            f"category:{definition['category_id']}",
            definition["id"],
            "category_membership",
            base_weight=1,
        )

    for article in articles:
        non_category_nodes = [node_id for node_id in article["node_ids"] if not node_id.startswith("category:")]
        for source, target in combinations(non_category_nodes, 2):
            add_edge(
                source,
                target,
                "article_cooccurrence",
                article_id=article["id"],
                source_name=article["source"]["name"],
            )

    for source, target, relation in CURATED_EDGES:
        add_edge(source, target, relation, base_weight=2)

    edges: list[dict[str, Any]] = []
    read_articles = {event["article_id"] for event in read_events}
    for item in edge_data.values():
        read_support = sum(article_id in read_articles for article_id in item["article_ids"])
        article_count = len(item["article_ids"])
        item["article_count"] = article_count
        item["source_count"] = len(item["source_names"])
        item["read_support"] = read_support
        item["weight"] = round(item.pop("base_weight") + math.log2(article_count + 1) + read_support * 0.35, 3)
        edges.append(item)
    edges.sort(key=lambda item: (-item["weight"], item["id"]))
    return nodes, edges


def build_navigation(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]], articles: list[dict[str, Any]]
) -> dict[str, Any]:
    article_by_id = {article["id"]: article for article in articles}
    edge_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        edge_by_node[edge["source"]].append(edge)
        edge_by_node[edge["target"]].append(edge)

    navigation: dict[str, Any] = {}
    for node in nodes:
        ranked_edges = sorted(edge_by_node[node["id"]], key=lambda item: (-item["weight"], item["id"]))
        neighbors = [
            edge["target"] if edge["source"] == node["id"] else edge["source"]
            for edge in ranked_edges[:8]
        ]
        current_articles = [
            article_by_id[article_id]
            for article_id in node["current_article_ids"]
            if article_id in article_by_id
        ]
        current_articles.sort(key=lambda item: item["published_at"], reverse=True)
        navigation[node["id"]] = {
            "neighbor_node_ids": neighbors,
            "article_ids": [article["id"] for article in current_articles[:12]],
        }
    return navigation


# [Views and user report]

def diverse_top_nodes(
    nodes: list[dict[str, Any]], score_key: str, *, limit: int, excluded_categories: set[str] | None = None
) -> list[dict[str, Any]]:
    excluded_categories = excluded_categories or set()
    candidates = [
        node
        for node in nodes
        if node["type"] != "category"
        and node["category_id"] not in excluded_categories
        and node["current_article_ids"]
    ]
    candidates.sort(key=lambda item: (-item[score_key], item["label"]))
    result: list[dict[str, Any]] = []
    per_category: Counter[str] = Counter()
    for node in candidates:
        if per_category[node["category_id"]] >= 2:
            continue
        x, y = HOME_TREND_POSITIONS[len(result)]
        result.append({"node_id": node["id"], "x": x, "y": y})
        per_category[node["category_id"]] += 1
        if len(result) == limit:
            break
    return result


def stable_unit_interval(value: str) -> float:
    """같은 입력에 항상 같은 0 이상 1 미만의 목업 계수를 반환한다."""
    digest = int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:12], 16)
    return digest / float(16**12)


def build_home_trend_periods(
    nodes: list[dict[str, Any]], reference_at: datetime
) -> dict[str, dict[str, Any]]:
    """기간 UI가 소비할 통계와 seed를 재현 가능한 목업 값으로 구성한다.

    원본 수집은 직전 3개월 비교까지 지원하지 않으므로 기사 원문을 추가로
    생성하지 않는다. 현재 수집량을 기준으로 기간별 부피와 비교 기준값만
    결정적으로 산출하며, 반환 계약에 provenance를 별도로 명시한다.
    """
    eligible_nodes = [
        node
        for node in nodes
        if node["type"] != "category" and node["current_article_ids"]
    ]
    periods: dict[str, dict[str, Any]] = {}

    for period_index, definition in enumerate(HOME_TREND_PERIODS):
        period_id = definition["id"]
        statistics: dict[str, dict[str, int | float]] = {}
        for node in eligible_nodes:
            base_count = len(node["current_article_ids"])
            volume_factor = 1.0 if period_id == "today" else (
                0.78 + stable_unit_interval(f"trend-volume|{period_id}|{node['id']}") * 0.44
            )
            article_count = max(
                1,
                round(base_count * definition["volume_multiplier"] * volume_factor),
            )
            target_growth = -12 + stable_unit_interval(
                f"trend-growth|{period_id}|{node['id']}"
            ) * 60
            previous_article_count = max(
                1,
                round(article_count / (1 + target_growth / 100)),
            )
            change_rate = round(
                (article_count - previous_article_count)
                / previous_article_count
                * 100
            )
            statistics[node["id"]] = {
                "article_count": article_count,
                "previous_article_count": previous_article_count,
                "change_rate": change_rate,
                "ranking_score": round(
                    article_count * (1 + max(change_rate, 0) / 100),
                    3,
                ),
            }

        if period_id == "today":
            candidates = sorted(
                eligible_nodes,
                key=lambda node: (-node["trend_score"], node["label"]),
            )
        else:
            candidates = sorted(
                eligible_nodes,
                key=lambda node: (
                    -statistics[node["id"]]["ranking_score"],
                    -statistics[node["id"]]["article_count"],
                    node["label"],
                ),
            )

        selected_nodes: list[dict[str, Any]] = []
        per_category: Counter[str] = Counter()
        for node in candidates:
            if per_category[node["category_id"]] >= 2:
                continue
            selected_nodes.append(node)
            per_category[node["category_id"]] += 1
            if len(selected_nodes) == len(HOME_TREND_POSITIONS):
                break

        position_shift = (period_index * 2) % len(HOME_TREND_POSITIONS)
        positions = (
            HOME_TREND_POSITIONS[position_shift:]
            + HOME_TREND_POSITIONS[:position_shift]
        )
        seed_nodes = []
        for node, (x, y) in zip(selected_nodes, positions):
            node_statistics = statistics[node["id"]]
            seed_nodes.append(
                {
                    "node_id": node["id"],
                    "x": x,
                    "y": y,
                    "article_count": node_statistics["article_count"],
                    "previous_article_count": node_statistics["previous_article_count"],
                    "change_rate": node_statistics["change_rate"],
                }
            )

        rising_node_ids = [
            entry["node_id"]
            for entry in sorted(
                seed_nodes,
                key=lambda entry: (
                    -entry["change_rate"],
                    -entry["article_count"],
                    entry["node_id"],
                ),
            )
            if entry["change_rate"] > 0
        ][:3]
        if len(rising_node_ids) < 3:
            rising_node_ids.extend(
                entry["node_id"]
                for entry in sorted(
                    seed_nodes,
                    key=lambda entry: (-entry["article_count"], entry["node_id"]),
                )
                if entry["node_id"] not in rising_node_ids
            )
            rising_node_ids = rising_node_ids[:3]

        window_days = definition["window_days"]
        periods[period_id] = {
            "id": period_id,
            "label": definition["label"],
            "title": definition["title"],
            "window_days": window_days,
            "window_label": definition["window_label"],
            "comparison_label": definition["comparison_label"],
            "starts_at": iso(reference_at - timedelta(days=window_days)),
            "ends_at": iso(reference_at),
            "comparison_starts_at": iso(reference_at - timedelta(days=window_days * 2)),
            "comparison_ends_at": iso(reference_at - timedelta(days=window_days)),
            "updated_at": iso(reference_at),
            "seed_nodes": seed_nodes,
            "rising_node_ids": rising_node_ids,
        }

    return periods


def build_views(
    nodes: list[dict[str, Any]], articles: list[dict[str, Any]], reference_at: datetime
) -> dict[str, Any]:
    for node in nodes:
        node["trend_score"] = len(node["current_article_ids"])
        node["personal_score"] = round(
            len(node["current_article_ids"]) * (0.4 + USER_INTERESTS[node["category_id"]]),
            3,
        )

    category_views = {}
    for category in CATEGORIES:
        candidates = [
            node
            for node in nodes
            if node["category_id"] == category["id"] and node["type"] != "category" and node["current_article_ids"]
        ]
        candidates.sort(key=lambda item: (-item["trend_score"], item["label"]))
        positions = [(0.12, 0.21), (0.40, 0.14), (0.71, 0.23), (0.25, 0.48), (0.59, 0.48), (0.84, 0.62), (0.43, 0.75), (0.13, 0.76)]
        category_views[category["id"]] = {
            "title": f"{category['name']} 분야별 탐색",
            "seed_nodes": [
                {"node_id": node["id"], "x": positions[index][0], "y": positions[index][1]}
                for index, node in enumerate(candidates[:8])
            ],
        }

    searchable_nodes = [node for node in nodes if node["type"] != "category"]
    searchable_nodes.sort(key=lambda item: (-item["trend_score"], item["label"]))
    trend_periods = build_home_trend_periods(nodes, reference_at)
    return {
        "home": {
            "trend_window": "최근 24시간",
            "updated_at": iso(reference_at),
            "trend_period_order": [period["id"] for period in HOME_TREND_PERIODS],
            "trend_statistics_provenance": {
                "kind": "deterministic_mock",
                "synthetic": True,
                "basis": "current_article_ids",
                "description": "현재 수집량을 기준으로 기간 부피와 직전 기간 비교값을 재현 가능하게 산출한 목업 통계",
            },
            "trend_periods": trend_periods,
            "today_trends": [
                {"node_id": entry["node_id"], "x": entry["x"], "y": entry["y"]}
                for entry in trend_periods["today"]["seed_nodes"]
            ],
            "for_you": diverse_top_nodes(nodes, "personal_score", limit=8, excluded_categories={"sports"}),
        },
        "categories": category_views,
        "search": {
            "placeholder": "기업, 인물, 정책, 주제를 검색하세요",
            "suggested_node_ids": [node["id"] for node in searchable_nodes[:20]],
            "article_search_fields": ["title", "description", "source.name"],
        },
    }


def add_navigation_events(read_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = list(read_events)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in read_events:
        grouped[event["session_id"]].append(event)
    for session_id, session_events in grouped.items():
        session_events.sort(key=lambda item: item["occurred_at"])
        path: list[str] = []
        for event in session_events:
            node_id = next((node_id for node_id in event["node_ids"] if not node_id.startswith("category:")), event["node_ids"][0])
            if node_id in path:
                continue
            path.append(node_id)
            events.append(
                {
                    "id": stable_id("event", f"node-open|{session_id}|{node_id}"),
                    "type": "node_open",
                    "user_id": event["user_id"],
                    "session_id": session_id,
                    "occurred_at": event["occurred_at"],
                    "node_id": node_id,
                    "path": list(path),
                    "synthetic": True,
                }
            )
    events.sort(key=lambda item: item["occurred_at"])
    return events


def build_user_report(
    read_events: list[dict[str, Any]], articles: list[dict[str, Any]], reference_at: datetime
) -> dict[str, Any]:
    article_by_id = {article["id"]: article for article in articles}
    cutoff = reference_at - timedelta(days=90)
    recent_reads = [event for event in read_events if parse_dt(event["occurred_at"]) >= cutoff]
    category_counts = Counter(event["primary_category_id"] for event in recent_reads)
    node_counts: Counter[str] = Counter(
        node_id
        for event in recent_reads
        for node_id in event["node_ids"]
        if not node_id.startswith("category:")
    )
    last_28_cutoff = reference_at - timedelta(days=28)
    previous_cutoff = reference_at - timedelta(days=56)
    recent_node_counts: Counter[str] = Counter()
    previous_node_counts: Counter[str] = Counter()
    for event in recent_reads:
        occurred = parse_dt(event["occurred_at"])
        target = recent_node_counts if occurred >= last_28_cutoff else previous_node_counts if occurred >= previous_cutoff else None
        if target is not None:
            target.update(node_id for node_id in event["node_ids"] if not node_id.startswith("category:"))

    terrain = []
    max_count = max(node_counts.values(), default=1)
    for node_id, count in node_counts.most_common(12):
        recent = recent_node_counts[node_id]
        previous = previous_node_counts[node_id]
        growth = (recent - previous) / max(1, previous)
        terrain.append(
            {
                "node_id": node_id,
                "x_read_frequency": round(count / max_count, 3),
                "y_recent_growth": round(max(-1.0, min(1.0, growth)), 3),
                "read_count": count,
            }
        )

    week_counts = [0] * 13
    for event in recent_reads:
        age_days = max(0, (reference_at - parse_dt(event["occurred_at"])).days)
        bucket = min(12, age_days // 7)
        week_counts[12 - bucket] += 1

    sessions = {event["session_id"] for event in recent_reads}
    real_current_reads = sum(not article_by_id[event["article_id"]]["synthetic"] for event in recent_reads)
    return {
        "period": {
            "label": "최근 3개월",
            "from": iso(cutoff),
            "to": iso(reference_at),
            "fixed": True,
        },
        "overview": {
            "articles_read": len(recent_reads),
            "topics_visited": len(node_counts),
            "exploration_sessions": len(sessions),
            "real_current_articles_read": real_current_reads,
        },
        "category_distribution": [
            {
                "category_id": category["id"],
                "category_name": category["name"],
                "count": category_counts[category["id"]],
                "ratio": round(category_counts[category["id"]] / max(1, len(recent_reads)), 4),
            }
            for category in CATEGORIES
        ],
        "weekly_reading": [
            {"week_index": index - 12, "count": count}
            for index, count in enumerate(week_counts)
        ],
        "recent_topic_terrain": {
            "x_axis": "최근 3개월 열람 빈도",
            "y_axis": "최근 4주 관심 증가율",
            "points": terrain,
        },
    }


def build_demo_scenarios(nodes: list[dict[str, Any]], navigation: dict[str, Any]) -> list[dict[str, Any]]:
    available = {node["id"] for node in nodes}
    scenarios = [
        {
            "id": "scenario:north-korea-security",
            "name": "북한에서 핵안보로",
            "path": ["entity:north-korea", "entity:defense-ministry", "topic:nuclear-security", "entity:united-states"],
        },
        {
            "id": "scenario:semiconductor-ai",
            "name": "반도체 공급망에서 AI로",
            "path": ["topic:semiconductor-industry", "topic:hbm", "entity:nvidia", "topic:gpu", "topic:artificial-intelligence"],
        },
        {
            "id": "scenario:hormuz-trump",
            "name": "호르무즈에서 미국 정치로",
            "path": ["entity:iran", "topic:strait-of-hormuz", "entity:united-states", "entity:donald-trump"],
        },
        {
            "id": "scenario:personal-ai-map",
            "name": "나의 기록 지도 AI 군집",
            "path": ["topic:artificial-intelligence", "topic:ai-chip", "topic:semiconductor-industry", "entity:sk-hynix", "topic:hbm"],
        },
    ]
    for scenario in scenarios:
        scenario["valid"] = all(node_id in available for node_id in scenario["path"])
        scenario["all_steps_navigable"] = all(
            right in navigation[left]["neighbor_node_ids"] or left in navigation[right]["neighbor_node_ids"]
            for left, right in zip(scenario["path"], scenario["path"][1:])
        )
    return scenarios


# [Validation and output]

def validate_dataset(dataset: dict[str, Any], original_rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    articles = dataset["articles"]
    nodes = dataset["nodes"]
    edges = dataset["edges"]
    events = dataset["user_events"]
    article_ids = {article["id"] for article in articles}
    node_ids = {node["id"] for node in nodes}
    category_ids = set(CATEGORY_BY_ID)

    if len(article_ids) != len(articles):
        errors.append("article ids are not unique")
    if len(node_ids) != len(nodes):
        errors.append("node ids are not unique")
    if sum(article["provider"] == "gnews" for article in articles) != len(original_rows):
        errors.append("not all original GNews articles were preserved")
    original_urls = {row["article_id"]: row.get("url") for row in original_rows}
    for article in articles:
        if article["primary_category_id"] not in category_ids:
            errors.append(f"invalid primary category: {article['id']}")
        if (
            not article["category_ids"]
            or article["primary_category_id"] not in article["category_ids"]
            or any(category_id not in category_ids for category_id in article["category_ids"])
        ):
            errors.append(f"invalid multi-label categories: {article['id']}")
        if any(node_id not in node_ids for node_id in article["node_ids"]):
            errors.append(f"invalid article node reference: {article['id']}")
        if article["synthetic"] and article.get("url"):
            errors.append(f"synthetic article exposes an external url: {article['id']}")
        if article["provider"] == "gnews":
            original_id = article["provenance"]["original_article_id"]
            if article.get("url") != original_urls[original_id]:
                errors.append(f"GNews url changed: {article['id']}")
    for edge in edges:
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            errors.append(f"invalid edge node reference: {edge['id']}")
    for event in events:
        if event["type"] == "article_read" and event["article_id"] not in article_ids:
            errors.append(f"invalid event article reference: {event['id']}")
        if event["type"] == "node_open" and event["node_id"] not in node_ids:
            errors.append(f"invalid event node reference: {event['id']}")

    eligible_current = Counter(
        category_id
        for article in articles
        if article["data_role"] in {"current", "current_supplement"} and article["mock_eligible"]
        for category_id in article["category_ids"]
    )
    for category_id in category_ids:
        if eligible_current[category_id] < MIN_CURRENT_ARTICLES_PER_CATEGORY:
            errors.append(f"category below target: {category_id}")

    home_view = dataset.get("views", {}).get("home", {})
    expected_period_ids = [period["id"] for period in HOME_TREND_PERIODS]
    period_order = home_view.get("trend_period_order")
    trend_periods = home_view.get("trend_periods")
    provenance = home_view.get("trend_statistics_provenance")
    if period_order != expected_period_ids:
        errors.append("invalid home trend period order")
    if not isinstance(provenance, dict) or provenance.get("kind") != "deterministic_mock":
        errors.append("missing home trend statistics provenance")
    if not isinstance(trend_periods, dict):
        errors.append("missing home trend periods")
    else:
        for period_id in expected_period_ids:
            period = trend_periods.get(period_id)
            if not isinstance(period, dict):
                errors.append(f"missing home trend period: {period_id}")
                continue
            if period.get("id") != period_id:
                errors.append(f"invalid home trend period id: {period_id}")
            seed_nodes = period.get("seed_nodes")
            rising_node_ids = period.get("rising_node_ids")
            if not isinstance(seed_nodes, list) or len(seed_nodes) != 8:
                errors.append(f"invalid home trend seed count: {period_id}")
                continue
            seed_node_ids = [entry.get("node_id") for entry in seed_nodes]
            if len(set(seed_node_ids)) != len(seed_node_ids):
                errors.append(f"duplicate home trend seed: {period_id}")
            if any(node_id not in node_ids for node_id in seed_node_ids):
                errors.append(f"invalid home trend node reference: {period_id}")
            if (
                not isinstance(rising_node_ids, list)
                or len(rising_node_ids) != 3
                or len(set(rising_node_ids)) != 3
                or not set(rising_node_ids).issubset(seed_node_ids)
            ):
                errors.append(f"invalid home rising nodes: {period_id}")
            else:
                seed_by_node_id = {
                    entry["node_id"]: entry for entry in seed_nodes
                }
                if any(
                    seed_by_node_id[node_id].get("change_rate", 0) <= 0
                    for node_id in rising_node_ids
                ):
                    errors.append(f"home rising node is not increasing: {period_id}")
            for entry in seed_nodes:
                x = entry.get("x")
                y = entry.get("y")
                article_count = entry.get("article_count")
                previous_count = entry.get("previous_article_count")
                change_rate = entry.get("change_rate")
                if not all(isinstance(value, (int, float)) for value in (x, y)):
                    errors.append(f"invalid home trend position: {period_id}")
                elif not 0 <= x <= 1 or not 0 <= y <= 1:
                    errors.append(f"home trend position out of range: {period_id}")
                if not isinstance(article_count, int) or article_count < 1:
                    errors.append(f"invalid home trend article count: {period_id}")
                if not isinstance(previous_count, int) or previous_count < 1:
                    errors.append(f"invalid home trend previous count: {period_id}")
                if not isinstance(change_rate, int):
                    errors.append(f"invalid home trend change rate: {period_id}")
                elif isinstance(article_count, int) and isinstance(previous_count, int) and previous_count > 0:
                    expected_change_rate = round(
                        (article_count - previous_count) / previous_count * 100
                    )
                    if change_rate != expected_change_rate:
                        errors.append(f"inconsistent home trend change rate: {period_id}")

    report_reads = dataset["user_report"]["overview"]["articles_read"]
    actual_reads = sum(event["type"] == "article_read" for event in events)
    if report_reads != actual_reads:
        errors.append("user report read count does not match read events")
    return errors


def build_coverage_report(
    articles: list[dict[str, Any]], supplement_counts: dict[str, int]
) -> dict[str, Any]:
    real = [article for article in articles if article["provider"] == "gnews"]
    current = [article for article in articles if article["data_role"] in {"current", "current_supplement"}]
    history = [article for article in articles if article["data_role"] == "personal_history"]
    return {
        "target_eligible_current_articles_per_category": MIN_CURRENT_ARTICLES_PER_CATEGORY,
        "real_gnews_total": len(real),
        "real_gnews_eligible": sum(article["mock_eligible"] for article in real),
        "real_gnews_by_primary_category": dict(
            Counter(article["primary_category_id"] for article in real)
        ),
        "real_gnews_multilabel_coverage": dict(
            Counter(category_id for article in real for category_id in article["category_ids"])
        ),
        "eligible_real_gnews_multilabel_coverage": dict(
            Counter(
                category_id
                for article in real
                if article["mock_eligible"]
                for category_id in article["category_ids"]
            )
        ),
        "classification_confidence": dict(
            Counter(article["classification"]["confidence"] for article in real)
        ),
        "current_supplements_by_category": supplement_counts,
        "eligible_current_by_category": dict(
            Counter(
                category_id
                for article in current
                if article["mock_eligible"]
                for category_id in article["category_ids"]
            )
        ),
        "historical_personal_records_by_primary_category": dict(
            Counter(article["primary_category_id"] for article in history)
        ),
        "quality_flags": dict(Counter(flag for article in real for flag in article["quality_flags"])),
        "total_articles_in_integrated_dataset": len(articles),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_rows = read_jsonl(args.input)
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    reference_at = parse_dt(metadata["started_at"])
    latest_published = max(parse_dt(row["published_at"]) for row in source_rows)
    reference_at = max(reference_at, latest_published + timedelta(hours=2))

    real_articles = normalize_real_articles(source_rows)
    current_supplements, supplement_counts = supplement_current_articles(real_articles, reference_at)
    history_articles, history_read_events = build_history_articles(reference_at)
    articles = [*real_articles, *current_supplements, *history_articles]

    current_read_events = select_current_reads(real_articles, reference_at)
    read_events = [*history_read_events, *current_read_events]
    user_events = add_navigation_events(read_events)
    stories = build_stories(articles)
    nodes, edges = build_graph(articles, read_events)
    navigation = build_navigation(nodes, edges, articles)
    views = build_views(nodes, articles, reference_at)
    user_report = build_user_report(read_events, articles, reference_at)
    coverage_report = build_coverage_report(articles, supplement_counts)
    review_queue = [
        {
            "article_id": article["id"],
            "title": article["title"],
            "primary_category_id": article["primary_category_id"],
            "primary_category_name": article["primary_category_name"],
            "category_ids": article["category_ids"],
            "category_names": article["category_names"],
            "classification": article["classification"],
        }
        for article in real_articles
        if article["classification"]["confidence"] == "low"
    ]

    dataset = {
        "schema_version": "1.1.0",
        "generated_at": iso(reference_at),
        "source_run_id": metadata["run_id"],
        "categories": CATEGORIES,
        "articles": articles,
        "stories": stories,
        "nodes": nodes,
        "edges": edges,
        "navigation": navigation,
        "views": views,
        "user": {
            "id": "user:demo-experienced",
            "display_name": "별빛 탐험가",
            "profile_type": "experienced_demo_user",
            "member_since": iso(reference_at - timedelta(days=120)),
            "interest_weights": USER_INTERESTS,
            "not_interested": ["sports"],
            "report_period_days": 90,
            "synthetic": True,
        },
        "user_events": user_events,
        "user_report": user_report,
        "demo_scenarios": build_demo_scenarios(nodes, navigation),
        "coverage_report": coverage_report,
        "disclosures": [
            "GNews 기사 294건의 제목, 출처, 링크와 발행시각은 수집 원본을 보존했습니다.",
            "서비스 카테고리는 규칙 기반 임시 분류이며 낮은 확신 결과는 review_queue.json에 분리했습니다.",
            "current_supplement와 personal_history는 시연용 합성 데이터이며 외부 원문 링크가 없습니다.",
            "노드, 엣지, 사용자 활동 및 리포트는 목업 동작 검증을 위한 파생·합성 데이터입니다.",
            "기간별 트렌드 기사 수와 비교 증감률은 현재 수집량에서 결정적으로 산출한 합성 목업 통계입니다.",
        ],
    }

    errors = validate_dataset(dataset, source_rows)
    if errors:
        raise RuntimeError("mock dataset validation failed:\n- " + "\n- ".join(errors))

    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "mock_dataset.json", dataset)
    write_json(args.output / "articles.json", articles)
    write_json(args.output / "stories.json", stories)
    write_json(args.output / "nodes.json", nodes)
    write_json(args.output / "edges.json", edges)
    write_json(args.output / "navigation.json", navigation)
    write_json(args.output / "views.json", views)
    write_json(args.output / "user.json", dataset["user"])
    write_json(args.output / "user_events.json", user_events)
    write_json(args.output / "user_report.json", user_report)
    write_json(args.output / "demo_scenarios.json", dataset["demo_scenarios"])
    write_json(args.output / "coverage_report.json", coverage_report)
    write_json(args.output / "review_queue.json", review_queue)
    write_json(
        args.output / "manifest.json",
        {
            "schema_version": dataset["schema_version"],
            "generated_at": dataset["generated_at"],
            "source_run_id": dataset["source_run_id"],
            "files": [
                "mock_dataset.json",
                "articles.json",
                "stories.json",
                "nodes.json",
                "edges.json",
                "navigation.json",
                "views.json",
                "user.json",
                "user_events.json",
                "user_report.json",
                "demo_scenarios.json",
                "coverage_report.json",
                "review_queue.json",
            ],
            "counts": {
                "articles": len(articles),
                "stories": len(stories),
                "nodes": len(nodes),
                "edges": len(edges),
                "user_events": len(user_events),
                "review_queue": len(review_queue),
            },
        },
    )
    print(json.dumps(coverage_report, ensure_ascii=False, indent=2))
    print(f"output: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
