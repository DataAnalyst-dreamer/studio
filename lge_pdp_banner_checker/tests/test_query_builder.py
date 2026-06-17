"""query_builder 모듈 테스트."""

from datetime import date

import pytest

from src.query_builder import (
    SKU_PAGE_QUERY,
    build_query,
    build_query_params,
    to_yyyymmdd,
)


def test_to_yyyymmdd_from_date():
    assert to_yyyymmdd(date(2026, 6, 1)) == "20260601"
    assert to_yyyymmdd(date(2026, 12, 31)) == "20261231"


def test_to_yyyymmdd_from_string():
    assert to_yyyymmdd("2026-06-01") == "20260601"
    assert to_yyyymmdd("2026/06/01") == "20260601"
    assert to_yyyymmdd("20260601") == "20260601"


def test_to_yyyymmdd_invalid():
    with pytest.raises(ValueError):
        to_yyyymmdd("2026-6")
    with pytest.raises(TypeError):
        to_yyyymmdd(20260601)


def test_build_query_params_ok():
    params = build_query_params(date(2026, 6, 1), date(2026, 6, 7))
    assert params == {"start_date": "20260601", "end_date": "20260607"}


def test_build_query_params_start_after_end():
    with pytest.raises(ValueError):
        build_query_params(date(2026, 6, 8), date(2026, 6, 1))


def test_build_query_returns_named_params():
    sql, params = build_query("2026-06-01", "2026-06-07")
    assert sql == SKU_PAGE_QUERY
    assert ":start_date" in sql
    assert ":end_date" in sql
    assert params["start_date"] == "20260601"
