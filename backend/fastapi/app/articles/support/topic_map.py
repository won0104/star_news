# AI가 반환하는 한글 대분류/소분류 라벨 -> 서비스 영문 코드 고정 매핑표

# classification.topic
TOPIC_NAME_TO_CODE: dict[str, str] = {
    "정치": "POLITICS",
    "경제": "ECONOMY",
    "사회": "SOCIETY",
    "문화": "CULTURE",
    "국제": "INTERNATIONAL",
    "스포츠": "SPORTS",
    "IT·과학": "IT_SCIENCE",
}

# classification.small_cls (KPF-bert-cls2 소분류, 대분류와 무관하게 라벨 자체가 고유함)
SUBTOPIC_NAME_TO_CODE: dict[str, str] = {
    # 정치
    "국회_정당": "NATIONAL_ASSEMBLY_PARTIES",
    "북한": "NORTH_KOREA",
    "선거": "ELECTIONS",
    "외교": "DIPLOMACY",
    "청와대": "PRESIDENTIAL_OFFICE",
    "행정_자치": "PUBLIC_ADMINISTRATION_LOCAL_GOVERNMENT",
    "정치일반": "POLITICS_GENERAL",
    # 경제
    "국제경제": "GLOBAL_ECONOMY",
    "금융_재테크": "FINANCE_INVESTMENT",
    "무역": "TRADE",
    "반도체": "SEMICONDUCTOR",
    "부동산": "REAL_ESTATE",
    "산업_기업": "INDUSTRY_BUSINESS",
    "서비스_쇼핑": "SERVICES_SHOPPING",
    "외환": "FOREIGN_EXCHANGE",
    "유통": "RETAIL_DISTRIBUTION",
    "자동차": "AUTOMOTIVE",
    "자원": "RESOURCES",
    "증권_증시": "STOCK_MARKET",
    "취업_창업": "EMPLOYMENT_STARTUPS",
    "경제일반": "ECONOMY_GENERAL",
    # 사회
    "교육_시험": "EDUCATION_EXAMS",
    "날씨": "WEATHER",
    "노동_복지": "LABOR_WELFARE",
    "미디어": "MEDIA",
    "사건_사고": "CRIME_ACCIDENTS",
    "여성": "WOMEN",
    "의료_건강": "HEALTHCARE_HEALTH",
    "장애인": "DISABILITY",
    "환경": "ENVIRONMENT",
    "사회일반": "SOCIETY_GENERAL",
    # 문화
    "미술_건축": "ART_ARCHITECTURE",
    "방송_연예": "BROADCAST_ENTERTAINMENT",
    "생활": "LIFESTYLE",
    "요리_여행": "FOOD_TRAVEL",
    "음악": "MUSIC",
    "전시_공연": "EXHIBITIONS_PERFORMANCES",
    "종교": "RELIGION",
    "출판": "PUBLISHING",
    "학술_문화재": "ACADEMIA_CULTURAL_HERITAGE",
    "문화일반": "CULTURE_GENERAL",
    # 국제
    "러시아": "RUSSIA",
    "미국_북미": "US_NORTH_AMERICA",
    "아시아": "ASIA",
    "유럽_EU": "EUROPE_EU",
    "일본": "JAPAN",
    "중국": "CHINA",
    "중남미": "LATIN_AMERICA",
    "중동_아프리카": "MIDDLE_EAST_AFRICA",
    "국제일반": "INTERNATIONAL_GENERAL",
    # 스포츠
    "골프": "GOLF",
    "농구_배구": "BASKETBALL_VOLLEYBALL",
    "야구_메이저리그": "BASEBALL_MLB",
    "야구_일본프로야구": "BASEBALL_NPB",
    "올림픽_아시안게임": "OLYMPICS_ASIAN_GAMES",
    "축구_월드컵": "FOOTBALL_WORLD_CUP",
    "축구_한국프로축구": "FOOTBALL_K_LEAGUE",
    "축구_해외축구": "FOOTBALL_INTERNATIONAL",
    "스포츠일반": "SPORTS_GENERAL",
    # IT_과학
    "과학": "SCIENCE",
    "모바일": "MOBILE",
    "보안": "SECURITY",
    "인터넷_SNS": "INTERNET_SOCIAL_MEDIA",
    "콘텐츠": "CONTENT",
    "IT_과학일반": "IT_SCIENCE_GENERAL",
}


def topic_code_from_name(topic_name: str | None) -> str | None:
    return TOPIC_NAME_TO_CODE.get(topic_name) if topic_name else None


def subtopic_code_from_name(small_cls_name: str | None) -> str | None:
    return SUBTOPIC_NAME_TO_CODE.get(small_cls_name) if small_cls_name else None
