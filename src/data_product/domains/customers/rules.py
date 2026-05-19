from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    name: str
    constraint: str
    severity: str  # critical | business_invalid | warning


CUSTOMER_RULES: list[Rule] = [
    Rule("customer_id_not_null", "customer_id IS NOT NULL", "critical"),
    Rule("valid_email_format", "email_std LIKE '%@%.%'", "business_invalid"),
    Rule("phone_not_null", "phone IS NOT NULL", "warning"),
]
