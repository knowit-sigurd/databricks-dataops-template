from data_product.domains.customers.rules import Rule as CustomerRule
from data_product.domains.customers.transformations import BRONZE_SCHEMA as CUSTOMERS_BRONZE_SCHEMA
from data_product.domains.gold.transformations import build_customer_orders
from data_product.domains.orders.transformations import BRONZE_SCHEMA as ORDERS_BRONZE_SCHEMA


def test_customers_bronze_schema():
    assert len(CUSTOMERS_BRONZE_SCHEMA) > 0


def test_orders_bronze_schema():
    assert len(ORDERS_BRONZE_SCHEMA) > 0
    amount_field = next(f for f in ORDERS_BRONZE_SCHEMA if f.name == "amount")
    assert str(amount_field.dataType) == "DecimalType(10,2)"


def test_rule_dataclass():
    rule = CustomerRule(name="no_nulls", constraint="customer_id IS NOT NULL", severity="critical")
    assert rule.severity == "critical"
    assert rule == CustomerRule(
        name="no_nulls", constraint="customer_id IS NOT NULL", severity="critical"
    )


def test_gold_transform_is_callable():
    assert callable(build_customer_orders)
