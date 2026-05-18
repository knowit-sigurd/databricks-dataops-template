from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    name: str
    constraint: str
    severity: str  # critical | business_invalid | warning


ORDER_RULES: list[Rule] = []
