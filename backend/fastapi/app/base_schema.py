# 모든 도메인 스키마가 상속하는 공용 베이스. 파이썬은 snake_case로 쓰고 JSON은 camelCase로 자동 변환한다.
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
