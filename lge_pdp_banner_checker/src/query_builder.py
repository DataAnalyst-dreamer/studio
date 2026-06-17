"""Redshift 쿼리 및 파라미터 생성 모듈.

기간 조건을 named parameter(:start_date, :end_date)로 바인딩하기 위한
SQL 문자열과 파라미터 딕셔너리를 생성한다. 날짜는 내부에서 YYYYMMDD
문자열로 변환된다(PRD 6.3 / 6.4).
"""

from __future__ import annotations

from datetime import date
from typing import Union

# 조회 결과 7개 컬럼 (PRD 6.1)
RESULT_COLUMNS = [
    "category",
    "catg_lvl1_nm",
    "catg_lvl2_nm",
    "catg_lvl3_nm",
    "sku",
    "clean_page_url",
    "vsit_pagenm",
]

# PRD 6.3 원본 쿼리. named parameter는 :start_date / :end_date 를 사용한다.
SKU_PAGE_QUERY = """
SELECT
    DISTINCT
    t3.catg_nm AS category,
    t3.catg_lvl1_nm AS catg_lvl1_nm,
    t3.catg_lvl2_nm AS catg_lvl2_nm,
    t3.catg_lvl3_nm AS catg_lvl3_nm,
    t1.sku AS sku,
    SPLIT_PART(t1.vsit_page_url, '?', 1) AS clean_page_url,
    t1.vsit_pagenm
FROM lge_bi_l1.l1ga_user_sesn_behv_dd_l t1
    LEFT JOIN lge_bi_l1.l1pr_prod_catg_m t2 ON t1.mdl_id = t2.mdl_id
    LEFT JOIN lge_bi_l1.l1pr_catg_m t3 ON t2.catg_id = t3.catg_id
WHERE 1=1
    AND t1.base_dt BETWEEN :start_date AND :end_date
    AND t1.evnt_nm = 'page_view'
    AND t1.cnts_grp2_nm = '스토어'
    AND t1.sku IS NOT NULL
    AND SPLIT_PART(vsit_pagenm, '|', 1) != '(not set)'
ORDER BY category
""".strip()


def to_yyyymmdd(value: Union[date, str]) -> str:
    """date 또는 'YYYY-MM-DD' 문자열을 'YYYYMMDD' 문자열로 변환한다.

    예: date(2026, 6, 1) -> '20260601', '2026-06-01' -> '20260601'
    """
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    if isinstance(value, str):
        cleaned = value.strip().replace("-", "").replace("/", "")
        if len(cleaned) != 8 or not cleaned.isdigit():
            raise ValueError(f"날짜 형식이 올바르지 않습니다: {value!r}")
        return cleaned
    raise TypeError(f"지원하지 않는 날짜 타입입니다: {type(value)!r}")


def build_query_params(
    start_date: Union[date, str], end_date: Union[date, str]
) -> dict[str, str]:
    """시작일/종료일을 YYYYMMDD named parameter 딕셔너리로 변환한다.

    시작일이 종료일보다 늦으면 ValueError를 발생시킨다(PRD 6.4 / FR-002).
    """
    start = to_yyyymmdd(start_date)
    end = to_yyyymmdd(end_date)
    if start > end:
        raise ValueError(
            f"시작일({start})은 종료일({end})보다 늦을 수 없습니다."
        )
    return {"start_date": start, "end_date": end}


def build_query(
    start_date: Union[date, str], end_date: Union[date, str]
) -> tuple[str, dict[str, str]]:
    """SQL과 named parameter 딕셔너리를 함께 반환한다."""
    params = build_query_params(start_date, end_date)
    return SKU_PAGE_QUERY, params
