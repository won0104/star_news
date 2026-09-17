from app.articles.support.entity_filter import is_noise_entity_name, normalize_entity_name


# 전각 문자/대소문자/따옴표류/연속 공백이 전부 정규화 규칙대로 통일되는지 확인
def test_normalize_entity_name_folds_width_and_case_and_strips_wrap_chars():
    assert normalize_entity_name("　ＡＢＣ　") == "abc"  # 전각 공백/문자 -> 반각 + 소문자
    assert normalize_entity_name('"삼성전자"') == "삼성전자"
    assert normalize_entity_name("  김민수   기자  ") == "김민수 기자"  # 연속 공백 축약


# None/빈 문자열이 예외 없이 빈 문자열로 정규화되는지 확인
def test_normalize_entity_name_handles_none_and_empty():
    assert normalize_entity_name(None) == ""
    assert normalize_entity_name("") == ""


# 빈 값/기호만 있는 스팬은 전부 노이즈로 걸러지는지 확인
def test_is_noise_entity_name_rejects_empty_and_symbol_only():
    assert is_noise_entity_name(None) is True
    assert is_noise_entity_name("") is True
    assert is_noise_entity_name("...") is True
    assert is_noise_entity_name("·") is True
    assert is_noise_entity_name('"') is True


# 대명사는 "정확히 일치"할 때만 노이즈이고, 대명사를 포함하는 고유명사는 노이즈가 아니어야 함
def test_is_noise_entity_name_rejects_exact_pronoun_match_only():
    assert is_noise_entity_name("그") is True
    assert is_noise_entity_name("저희") is True
    # 대명사를 "포함"만 하는 실제 고유명사는 노이즈가 아니어야 함
    assert is_noise_entity_name("그린벨트") is False


# 정상적인 고유명사는 노이즈로 안 걸러지는지 확인 (오탐 방지 확인용)
def test_is_noise_entity_name_accepts_real_names():
    assert is_noise_entity_name("삼성전자") is False
    assert is_noise_entity_name("서울시청") is False
    assert is_noise_entity_name("김민수") is False


# "해당 국가들은", "이들 기업"처럼 지시 표현이 첫 단어면, 뒤에 명사/조사가 붙어도 노이즈여야 함
def test_is_noise_entity_name_rejects_referential_prefix_phrases():
    assert is_noise_entity_name("해당 국가들은") is True
    assert is_noise_entity_name("이들 기업") is True
    assert is_noise_entity_name("그들 회사") is True


# 지시 표현 단어가 "첫 단어"가 아니라 이름 일부로 포함된 경우엔 노이즈가 아니어야 함 (오탐 방지)
def test_is_noise_entity_name_accepts_names_containing_referential_word_not_as_first_word():
    assert is_noise_entity_name("해당화 축제") is False  # "해당"이 아니라 "해당화"라 다른 단어
    assert is_noise_entity_name("국가정보원") is False


# 대명사에 조사만 붙은 형태("그는", "그를", "제가")도 노이즈여야 함
def test_is_noise_entity_name_rejects_pronoun_with_particle():
    assert is_noise_entity_name("그는") is True
    assert is_noise_entity_name("그를") is True
    assert is_noise_entity_name("제가") is True
    # 대명사가 아닌 이름이 우연히 조사로 끝나는 경우는 노이즈가 아니어야 함
    assert is_noise_entity_name("삼성전자는") is False
