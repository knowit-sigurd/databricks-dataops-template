from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    name: str
    constraint: str
    severity: str  # critical | business_invalid | warning


ORDER_RULES: list[Rule] = [
    Rule("order_id_not_null", "order_id IS NOT NULL", "critical"),
    Rule("customer_id_not_null", "customer_id IS NOT NULL", "critical"),
    Rule("positive_amount", "amount > 0", "business_invalid"),
    Rule("status_not_null", "status_std IS NOT NULL", "warning"),
]
