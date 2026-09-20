"""Temporal occurrence와 별개인 materializable identity key 계약."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, order=True, slots=True)
class TemporalIdentityKey:
    value: str
    granularity: str
    semantic_type: str
    timezone: str | None

    def parts(self) -> tuple[str, str, str, str]:
        return self.value, self.granularity, self.semantic_type, self.timezone or ""


def normalized_temporal_key(
    normalization: Mapping[str, Any], *, semantic_type: str = "POINT",
    timezone: str | None = None,
) -> TemporalIdentityKey | None:
    """POINT 정규화 성공만 identity를 만든다; unresolved evidence는 그대로 둔다."""
    value = normalization.get("value", normalization.get("normalized_value"))
    granularity = normalization.get("granularity")
    if (normalization.get("status", normalization.get("normalization_status")) != "NORMALIZED"
        or not value or not granularity or semantic_type != "POINT"):
        return None
    expressed_zone = timezone if timezone is not None else normalization.get("timezone")
    return TemporalIdentityKey(str(value), str(granularity), semantic_type,
                               str(expressed_zone) if expressed_zone else None)
