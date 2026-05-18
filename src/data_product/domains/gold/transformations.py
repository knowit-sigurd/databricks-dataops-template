from pyspark.sql import DataFrame


def build_customer_orders(
    customers_silver: DataFrame,
    orders_silver: DataFrame,
) -> DataFrame:
    raise NotImplementedError
