import pandas as pd
import psycopg2


class SQLExecutor:
    def __init__(self, host, port, database, user, password):
        self.conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        )

    def execute(self, sql):
        return pd.read_sql_query(sql, self.conn)