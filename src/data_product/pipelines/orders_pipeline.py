from pyspark import pipelines as dp


@dp.table
def orders_bronze():
    pass


@dp.table
def orders_silver():
    pass


@dp.table
def orders_rejected():
    pass
