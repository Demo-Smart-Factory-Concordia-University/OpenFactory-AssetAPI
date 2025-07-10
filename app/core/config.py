# app/core/config.py
import os
from openfactory.kafka import KSQLDBClient

KSQLDB_URL = os.environ.get("KSQLDB_URL", "http://localhost:8088")
ksql = KSQLDBClient(KSQLDB_URL)
