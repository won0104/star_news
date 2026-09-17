# 추출한 Entity 중 노이즈(대명사/따옴표뿐인 스팬)를 걸러내고 이름을 정규화한다.
from __future__ import annotations

import re
import unicodedata

# 전체 스팬이 대명사/친족 호칭뿐인 경우 걸러냄
ENTITY_PRONOUNS: frozenset[str] = frozenset(
    {
        "그", "그녀", "그들", "그녀들", "그이", "그분", "이", "저", "얘", "걔", "쟤",
        "이쪽", "그쪽", "저쪽", "나", "너", "우리", "저희", "당신", "본인", "자신", "자기", "자기들", "여러분",
        "제", "내",
        "형", "동생", "누나", "언니", "오빠", "형님", "아우", "형수", "제수", "시동생", "처남", "매형",
        "고모", "이모", "삼촌", "외삼촌", "할아버지", "할머니", "아버지", "어머니", "아빠", "엄마",
        "아들", "딸", "남편", "아내", "부인", "배우자",
    }
)

# "해당 국가들은", "이들 기업"처럼 지시 표현으로 시작하는 스팬 - 뒤에 어떤 명사가 붙어도 특정 개체명이 아니라
# 앞서 언급된 대상을 다시 가리키는 표현이라 노이즈로 간주
# 실제 데이터에서 확인된 것만 등록
ENTITY_REFERENTIAL_PREFIXES: frozenset[str] = frozenset({"이들", "그들", "해당"})

# "그는", "그를"처럼 대명사에 조사만 붙은 형태를 노이즈로 잡기 위해 시험 삼아 떼어볼 조사 목록
# (실제 저장되는 이름은 안 건드림 - 노이즈 판별에만 씀)
_TRAILING_PARTICLES: tuple[str, ...] = ("은", "는", "이", "가", "을", "를", "의", "도")

_QUOTE_AND_WRAP = "\"'“”‘’「」『』[]()（）〈〉<>《》·…⋯–—-"


# NFKC 정규화(전각/반각 등 호환 문자까지 통일) + 영문 대소문자 통일 + 앞뒤 공백/따옴표류 제거 + 내부 연속 공백 축약
def normalize_entity_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", str(name or "")).casefold().strip()
    text = text.strip(_QUOTE_AND_WRAP).strip()
    text = re.sub(r"\s+", " ", text)
    return text


# 이 이름이 Entity 노드로 만들면 안 되는 노이즈인지 판별한다 (빈 값/기호뿐/대명사)
def is_noise_entity_name(name: str | None) -> bool:
    if name is None:
        return True

    # 유니코드 정규화(전각/반각 등 호환 문자까지 통일) + 공백 제거
    raw = unicodedata.normalize("NFKC", str(name)).strip()
    if not raw:
        return True

    # 숫자/영문/한글이 하나도 없으면(따옴표·기호만 있으면, 예: "...", "·") 노이즈
    if not re.search(r"[0-9A-Za-z가-힣]", raw):
        return True

    # 따옴표/괄호류까지 제거
    core = normalize_entity_name(raw)
    if not core:
        return True

    # 문자/숫자가 없으면(위에서 못 걸러낸 특수 케이스 방지) 노이즈
    if not re.search(r"[0-9A-Za-z가-힣]", core):
        return True

    # 문장부호 하나면(따옴표 벗기다 남은 잔재) 노이즈
    if len(core) == 1 and not re.match(r"[0-9A-Za-z가-힣]", core):
        return True

    # 부분 포함이 아니라 정규화된 이름 전체가 대명사/친족 호칭과 정확히 일치할 때만 노이즈
    if core in ENTITY_PRONOUNS:
        return True

    # 대명사 + 조사 결합형("그는", "그를") - 조사 하나를 떼어봤을 때 대명사와 정확히 일치하면 노이즈
    # (저장되는 이름 자체를 바꾸는 게 아니라 노이즈 판별에만 씀)
    for particle in _TRAILING_PARTICLES:
        if core.endswith(particle) and core[: -len(particle)] in ENTITY_PRONOUNS:
            return True

    # 첫 단어가 지시 표현이면(뒤에 명사가 오든 안 오든) 노이즈
    first_word = core.split(" ", 1)[0]
    if first_word in ENTITY_REFERENTIAL_PREFIXES:
        return True

    return False
