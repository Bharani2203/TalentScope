"""Explicit role aliases backed by O*NET occupations present in local SQLite."""

from __future__ import annotations

import re
import sqlite3
from typing import Any


# Values are SOC identifiers found in this repository's local O*NET reference DB.
# Titles are deliberately read from SQLite at resolution time, never inferred here.
ROLE_ALIAS_SOC_CODES: dict[str, str] = {
    "data engineer": "15-1243.01",
    "data engineers": "15-1243.01",
    "machine learning engineer": "15-2051.00",
    "ml engineer": "15-2051.00",
    "data scientist": "15-2051.00",
    "data scientists": "15-2051.00",
    "backend developer": "15-1252.00",
    "back-end developer": "15-1252.00",
    "backend developers": "15-1252.00",
    "back-end developers": "15-1252.00",
    "frontend developer": "15-1254.00",
    "front-end developer": "15-1254.00",
    "frontend developers": "15-1254.00",
    "front-end developers": "15-1254.00",
    "devops engineer": "15-1244.00",
    "devops engineers": "15-1244.00",
    "data analyst": "15-2051.01",
    "data analysts": "15-2051.01",
}


def normalize_role_alias(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9+#.\s-]", " ", value.strip().casefold())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    aliases = {
        "ml engineer": "machine learning engineer",
        "ml engineers": "machine learning engineer",
        "machine-learning engineer": "machine learning engineer",
        "machine-learning engineers": "machine learning engineer",
        "back end engineer": "backend engineer",
        "back-end engineer": "backend engineer",
        "front end engineer": "frontend engineer",
        "front-end engineer": "frontend engineer",
    }
    normalized = aliases.get(normalized, normalized)
    for plural, singular in (
        (" engineers", " engineer"), (" developers", " developer"),
        (" analysts", " analyst"), (" scientists", " scientist"),
        (" architects", " architect"), (" designers", " designer"),
        (" managers", " manager"),
    ):
        if normalized.endswith(plural):
            normalized = normalized[:-len(plural)] + singular
            break
    return normalized


def role_alias_soc_code(value: str) -> str | None:
    return ROLE_ALIAS_SOC_CODES.get(normalize_role_alias(value))


def query_local_onet_occupation(connection: Any, soc_code: str) -> dict[str, str] | None:
    """Confirm an alias target exists in the configured local O*NET database."""
    try:
        row = connection.execute(
            "SELECT soc_code, title FROM ref_onet_occupations WHERE soc_code = ? LIMIT 1",
            (soc_code,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or str(row["soc_code"]) != soc_code or not str(row["title"]).strip():
        return None
    return {"soc_code": str(row["soc_code"]), "title": str(row["title"]).strip()}
