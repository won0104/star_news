"""Immutable explicit Event blocking policy, separate from the v2.2 reference default.

The source audit digest is provenance. Runtime retrieval reads only this frozen
numeric config and current request EventSignals, never saved audit pairs or Gold.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path

from .event_monotonic import MonotonicEventPolicy


@dataclass(frozen=True, slots=True)
class EventIdentityBoundedContract:
    policy_id: str
    source_shadow_policy_id: str
    source_shadow_policy_sha256: str
    config_sha256: str
    router_policy: MonotonicEventPolicy

    @classmethod
    def from_config(cls, path: str | Path) -> "EventIdentityBoundedContract":
        data = Path(path).read_bytes()
        value = json.loads(data)
        if (value.get("schema_version") != "articlelocal-bcr-event-monotonic-bounded-v1"
            or value.get("mode") != "EXPLICIT_BOUNDED"
            or value.get("published") is not False):
            raise ValueError("Event blocking config must be explicit, unpublished bounded mode")
        shadow = MonotonicEventPolicy()
        expected = asdict(shadow)
        expected.pop("policy_id")
        if value.get("numerical_contract") != expected:
            raise ValueError("Event bounded parameters differ from frozen shadow policy")
        source_id = str(value.get("source_shadow_policy_id", ""))
        source_sha = str(value.get("source_shadow_policy_sha256", ""))
        if (source_id != shadow.policy_id or len(source_sha) != 64
            or any(character not in "0123456789abcdef" for character in source_sha)):
            raise ValueError("Event shadow policy provenance is invalid")
        policy_id = str(value.get("production_policy_id", ""))
        if policy_id != "BCR_C_MONOTONIC_SEED_CLIQUE_V1":
            raise ValueError("Unknown Event production policy ID")
        router = MonotonicEventPolicy(policy_id=policy_id, **expected)
        router.validate()
        return cls(policy_id, source_id, source_sha, sha256(data).hexdigest(), router)
