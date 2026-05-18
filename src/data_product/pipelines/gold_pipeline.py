from pyspark import pipelines as dp


@dp.materialized_view
def customer_orders_gold():
    pass
