from app.articles.repository import _has_event_conflict


# Actor/Target이 겹치면(같은 사건일 가능성) 충돌로 판단하지 않아야 함
def test_no_conflict_when_actor_target_overlap():
    assert _has_event_conflict(["정부", "기업A"], ["국민"], ["정부"], ["국민"]) is False


# 등장인물이 완전히 겹치지 않으면(2명 이상씩) 서로 다른 사건으로 판단
def test_conflict_when_both_have_two_plus_actors_but_disjoint():
    assert _has_event_conflict(["정부", "기업A"], [], ["삼성전자", "SK하이닉스"], []) is True


# 한쪽이라도 Actor가 1명뿐이면 "겹치는 사람 없음"만으로 다른 사건이라 단정하지 않음 (오탐 방지)
def test_no_conflict_when_actor_count_below_two():
    assert _has_event_conflict(["정부"], [], ["기업A"], []) is False


# 같은 주체(정부)가 등장해도, 대상이 완전히 다르면(기업A vs 기업B) 다른 사건 - "누구를 제재했나" 패턴
def test_conflict_when_targets_disjoint():
    assert _has_event_conflict(["정부"], ["기업A"], ["정부"], ["기업B"]) is True


# Target 정보가 한쪽이라도 없으면 그것만으로 충돌 판단하지 않음
def test_no_conflict_when_target_missing_on_either_side():
    assert _has_event_conflict(["정부"], [], ["정부"], ["기업A"]) is False


# Actor/Target 정보가 아예 없으면(둘 다 빈 리스트) 충돌 판단 근거가 없으니 충돌 아님
def test_no_conflict_when_both_actor_and_target_empty():
    assert _has_event_conflict([], [], [], []) is False
