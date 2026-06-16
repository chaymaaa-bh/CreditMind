from __future__ import annotations

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        )
    return _driver


def run_cypher(cypher: str, params: dict | None = None) -> list[dict]:
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    with _get_driver().session(database=database) as session:
        return [dict(r) for r in session.run(cypher, params or {})]
