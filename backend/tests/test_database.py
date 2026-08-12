from __future__ import annotations

from sqlalchemy import inspect


def test_required_price_table_exists(db_engine):
    tables = inspect(db_engine).get_table_names()
    assert "prices" in tables

    columns = {column["name"] for column in inspect(db_engine).get_columns("prices")}
    assert {"id", "date", "store", "product", "price"}.issubset(columns)
