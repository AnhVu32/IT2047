from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.sql import text


class PostgresConnector:
    def __init__(self, config: dict):
        self.config = config
        self.engine = None
        self.connection_string = None
        self.dbname = None
        self.port = None
        self.host = None
        self.password = None
        self.username = None

    def start(self):
        self.username, self.password, self.host, self.port, self.dbname, statement_timeout = self.config["username_db"], \
            self.config[
                "password_db"], \
            self.config["host_db"], self.config["port_db"], self.config["database"], 100
        self.connection_string = f'postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.dbname}'
        self.engine = create_engine(self.connection_string, pool_size=5000, max_overflow=12000)

    def execute_raw_query(self, raw_query: str, **kwargs):
        try:
            query = text(raw_query)
            rr = self.engine.execute(query, **kwargs).fetchall()
            if len(rr) == 0:
                return None
            res = [tuple(i) for i in rr]
            return res
        except Exception as e:
            logger.error(f"execute_raw_query ex: {e}")
            return None

    def fetch_mappings(self, raw_query: str, **kwargs):
        """Execute a read query and preserve column names.

        Unlike the legacy method, errors are not converted to an empty result. Search
        must distinguish an unavailable database from a valid no-result response.
        """
        query = text(raw_query)
        with self.engine.connect() as connection:
            result = connection.execute(query, kwargs)
            return [dict(row) for row in result.mappings().all()]

    def execute_write(self, raw_query: str, **kwargs):
        query = text(raw_query)
        with self.engine.begin() as connection:
            return connection.execute(query, kwargs)

    def fetch_write(self, raw_query: str, **kwargs):
        """Execute a write inside a transaction and return any produced rows.

        Use for parameterized ``INSERT ... RETURNING``/``UPDATE ... RETURNING``
        statements where the caller needs the committed row back.
        """
        query = text(raw_query)
        with self.engine.begin() as connection:
            result = connection.execute(query, kwargs)
            if not result.returns_rows:
                return []
            return [dict(row) for row in result.mappings().all()]

    def execute_write_many(self, raw_query: str, rows: list):
        """Execute one parameterized write per row inside a single transaction."""
        if not rows:
            return 0
        query = text(raw_query)
        with self.engine.begin() as connection:
            connection.execute(query, rows)
        return len(rows)

    def stop(self):
        self.engine.dispose()
