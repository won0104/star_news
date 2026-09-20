"""Article-local bounded routing의 공통 계약과 독립 shadow 관찰 경계.

기본 v2.2 pipeline은 이 계층을 아직 호출하지 않는다. Lane adapter는 selected ID만
fine scorer에 전달하고, capture는 마지막 실제 소비 전에 독립 sink로 보낸다.
"""

from .core import (
    ArticleCandidateIndex, BudgetRouter, IndexedCandidate, RouteDecision,
    RequestBudget, RouteKeys, RoutingExecutionLedger, RoutingMode,
    RoutingPolicy, RoutingSummary, TierBudget, nested_tier_prefix,
)
from .observer import RoutingObservation, StreamingRoutingObserver

__all__ = (
    "ArticleCandidateIndex", "BudgetRouter", "IndexedCandidate", "RouteDecision",
    "RequestBudget", "RouteKeys", "RoutingExecutionLedger", "RoutingMode",
    "RoutingPolicy", "RoutingSummary", "TierBudget", "nested_tier_prefix",
    "RoutingObservation", "StreamingRoutingObserver",
)
