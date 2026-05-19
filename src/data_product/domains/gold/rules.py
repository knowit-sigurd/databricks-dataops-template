from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    name: str
    constraint: str
    severity: str  # critical | business_invalid | warning


GOLD_RULES: list[Rule] = [
    Rule("customer_id_not_null", "customer_id IS NOT NULL", "critical"),
    Rule("non_negative_order_count", "order_count >= 0", "business_invalid"),
]
