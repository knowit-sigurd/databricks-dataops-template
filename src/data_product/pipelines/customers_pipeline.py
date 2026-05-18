from pyspark import pipelines as dp


@dp.table
def customers_bronze():
    pass


@dp.table
def customers_silver():
    pass


@dp.table
def customers_rejected():
    pass
