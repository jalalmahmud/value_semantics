import pandas as pd
import psycopg2

from value_semantics.profilers.dataframe import DataFrameProfiler


class PostgresConnector:
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        schema: str = "public",
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.schema = schema

    def _connect(self):
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.database,
            user=self.user,
            password=self.password,
        )

    def list_tables(self):
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (self.schema,))
                rows = cur.fetchall()

        return [row[0] for row in rows]

    def profile_table(self, table_name: str, sample_size: int = 1000):
        query = f'''
        SELECT *
        FROM "{self.schema}"."{table_name}"
        LIMIT {int(sample_size)}
        '''

        with self._connect() as conn:
            df = pd.read_sql_query(query, conn)

        return DataFrameProfiler().profile(
            df,
            table_name=table_name,
            sample_size=sample_size,
        )

    def profile_database(self, sample_size: int = 1000):
        profiles = {}

        for table_name in self.list_tables():
            profiles[table_name] = self.profile_table(
                table_name=table_name,
                sample_size=sample_size,
            )

        return profiles