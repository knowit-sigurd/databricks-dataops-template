from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def build_customer_orders(
    customers_silver: DataFrame,
    orders_silver: DataFrame,
) -> DataFrame:
    orders_agg = orders_silver.groupBy("customer_id").agg(
        F.count("order_id").alias("order_count"),
        F.sum("amount").alias("total_amount"),
        F.max("order_date").alias("last_order_date"),
    )
    return (
        customers_silver
        .join(orders_agg, on="customer_id", how="left")
        .select(
            F.col("customer_id"),
            F.col("name_std"),
            F.col("email_std"),
            F.col("region"),
            F.coalesce(F.col("order_count"), F.lit(0)).alias("order_count"),
            F.col("total_amount"),
            F.col("last_order_date"),
        )
    )
