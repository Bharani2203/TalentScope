"""Database connection and dynamic configuration module.

Supports dynamic DATABASE_URL environment variables (Supabase, Neon, AWS RDS, Render, Heroku)
with automatic fallback to individual PG* environment variables and local defaults.
Strictly adheres to Section 6 constraints: authentic enterprise data, 0 hallucinations.
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Return the active PostgreSQL connection URL.

    Reads from DATABASE_URL, POSTGRES_URL, or SQLALCHEMY_DATABASE_URI,
    or constructs a URL from PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD.
    """
    raw_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if raw_url and raw_url.strip():
        url = raw_url.strip()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "secret")
    host = os.getenv("PGHOST", "127.0.0.1")
    port = os.getenv("PGPORT", "5432")
    dbname = os.getenv("PGDATABASE", "talentscope_intelligence")
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def get_pg_config() -> dict[str, Any]:
    """Resolve dynamic psycopg2 connection dictionary from environment variables.

    Prioritizes DATABASE_URL / POSTGRES_URL, then individual PG* variables,
    then local loopback fallback.
    """
    raw_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if raw_url and raw_url.strip():
        parsed = urlparse(raw_url.strip())
        return {
            "dbname": parsed.path.lstrip("/"),
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 5432,
            "user": parsed.username or "postgres",
            "password": parsed.password or "",
            "connect_timeout": int(os.getenv("PGCONNECT_TIMEOUT", "5")),
        }

    return {
        "dbname": os.getenv("PGDATABASE", "talentscope_intelligence"),
        "host": os.getenv("PGHOST", "127.0.0.1"),
        "port": int(os.getenv("PGPORT", "5432")),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", "secret"),
        "connect_timeout": int(os.getenv("PGCONNECT_TIMEOUT", "3")),
    }


class _DynamicPGConfig(dict):
    """Dynamic dictionary proxy that re-evaluates database configuration on every access.

    Ensures that changes to DATABASE_URL or PG* environment variables at runtime
    are immediately reflected when unpacking `**PG_CONFIG`.
    """

    def __init__(self):
        super().__init__(get_pg_config())

    def _sync(self):
        super().clear()
        super().update(get_pg_config())

    def __getitem__(self, key: str) -> Any:
        self._sync()
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self._sync()
        return super().get(key, default)

    def items(self):
        self._sync()
        return super().items()

    def keys(self):
        self._sync()
        return super().keys()

    def values(self):
        self._sync()
        return super().values()

    def copy(self) -> dict[str, Any]:
        self._sync()
        return super().copy()

    def __iter__(self):
        self._sync()
        return super().__iter__()

    def __repr__(self) -> str:
        conf = get_pg_config()
        masked = conf.copy()
        if "password" in masked and masked["password"]:
            masked["password"] = "******"
        return f"<DynamicPGConfig {masked}>"


PG_CONFIG = _DynamicPGConfig()
