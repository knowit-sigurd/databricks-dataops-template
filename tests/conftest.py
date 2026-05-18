import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    return (
        SparkSession.builder
        .master("local[1]")
        .appName("dataops-tests")
        .getOrCreate()
    )
