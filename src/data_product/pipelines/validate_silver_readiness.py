# Databricks notebook source
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

catalog = dbutils.widgets.get("catalog")
target_schema = dbutils.widgets.get("target_schema")

ops_table = f"{catalog}.{target_schema}.ops_pipeline_run_log"
