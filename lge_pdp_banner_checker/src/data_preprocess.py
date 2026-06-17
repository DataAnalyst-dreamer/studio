"""URL 전처리 및 PDP 판별 모듈.

조회 결과에서 실제 PDP URL만 점검 대상으로 남기고, 카테고리/스토어/
비정상 URL은 EXCLUDED로 분류한다. sku + clean_page_url 기준 중복을
제거한다(PRD 8.5 / FR-005).
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import pandas as pd

from .query_builder import RESULT_COLUMNS

# 비PDP로 간주하여 제외할 URL 경로 패턴 (대소문자 무시).
# 더 구체적인 패턴(/m/category/)을 먼저 검사해야 정확한 사유가 부여된다.
EXCLUDED_PATH_PATTERNS = (
    "/m/category/",
    "/category/",
    "/store/",
)

# 정상 PDP로 인정할 LG전자 도메인 (서브도메인 포함 허용)
ALLOWED_DOMAINS = (
    "lge.co.kr",
    "lg.co.kr",
    "lge.com",
)

EXCLUDED_STATUS = "EXCLUDED"


def _normalize_url(url: Optional[str]) -> str:
    """URL 앞뒤 공백/쿼리스트링을 제거해 정규화한다."""
    if url is None or (isinstance(url, float) and pd.isna(url)):
        return ""
    text = str(url).strip()
    if not text:
        return ""
    # 쿼리스트링/프래그먼트 제거 (clean_page_url이지만 방어적으로 처리)
    text = text.split("?", 1)[0].split("#", 1)[0]
    return text.rstrip()


def _domain_allowed(url: str) -> bool:
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if not netloc:
        # 스킴 없는 상대경로 등은 도메인 판별 불가 → 비정상으로 간주
        return False
    host = netloc.split("@")[-1].split(":")[0]
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def classify_url(url: Optional[str]) -> tuple[bool, str]:
    """단일 URL이 점검 대상(PDP)인지 판별한다.

    Returns:
        (is_pdp, reason)
        - is_pdp가 False면 reason은 EXCLUDED 사유 문자열.
        - is_pdp가 True면 reason은 "".
    """
    clean = _normalize_url(url)
    if not clean:
        return False, "EMPTY_URL"

    lowered = clean.lower()
    for pattern in EXCLUDED_PATH_PATTERNS:
        if pattern in lowered:
            return False, f"NON_PDP_URL:{pattern}"

    if not _domain_allowed(clean):
        return False, "NON_LGE_DOMAIN"

    # PDP는 도메인 뒤 경로 세그먼트가 최소 1개 이상 존재해야 한다.
    parsed = urlparse(clean)
    path_segments = [seg for seg in parsed.path.split("/") if seg]
    if not path_segments:
        return False, "NO_PRODUCT_PATH"

    return True, ""


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """조회 DataFrame을 전처리한다.

    - clean_page_url 정규화
    - sku + clean_page_url 기준 중복 제거
    - PDP 여부 판정 컬럼(is_pdp, exclude_reason) 추가

    EXCLUDED 행도 결과에서 관리할 수 있도록 제거하지 않고 플래그만 부여한다.
    """
    if df is None or df.empty:
        cols = RESULT_COLUMNS + ["is_pdp", "exclude_reason"]
        return pd.DataFrame(columns=cols)

    work = df.copy()

    # 7개 컬럼 보장
    for col in RESULT_COLUMNS:
        if col not in work.columns:
            work[col] = pd.NA

    work["clean_page_url"] = work["clean_page_url"].map(_normalize_url)

    # 중복 제거: sku + clean_page_url
    work = work.drop_duplicates(subset=["sku", "clean_page_url"], keep="first")

    classified = work["clean_page_url"].map(classify_url)
    work["is_pdp"] = classified.map(lambda r: r[0])
    work["exclude_reason"] = classified.map(lambda r: r[1])

    return work.reset_index(drop=True)


def split_targets(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """전처리 결과를 (점검 대상, 제외 대상)으로 분리한다."""
    if df is None or df.empty or "is_pdp" not in df.columns:
        empty = df.copy() if df is not None else pd.DataFrame()
        return empty, empty.iloc[0:0] if not empty.empty else empty
    targets = df[df["is_pdp"]].reset_index(drop=True)
    excluded = df[~df["is_pdp"]].reset_index(drop=True)
    return targets, excluded


def apply_category_filter(
    df: pd.DataFrame,
    category: Optional[list] = None,
    catg_lvl1_nm: Optional[list] = None,
    catg_lvl2_nm: Optional[list] = None,
    catg_lvl3_nm: Optional[list] = None,
) -> pd.DataFrame:
    """계층형 카테고리 다중 선택 필터를 적용한다(FR-004).

    각 인자는 선택된 값들의 리스트이며, 비어 있으면 해당 계층은 필터하지 않는다.
    """
    if df is None or df.empty:
        return df

    filtered = df.copy()
    selections = {
        "category": category,
        "catg_lvl1_nm": catg_lvl1_nm,
        "catg_lvl2_nm": catg_lvl2_nm,
        "catg_lvl3_nm": catg_lvl3_nm,
    }
    for column, selected in selections.items():
        if selected:
            filtered = filtered[filtered[column].isin(selected)]
    return filtered.reset_index(drop=True)


def unique_values(df: pd.DataFrame, column: str) -> list:
    """카테고리 multiselect 후보용 고유값(정렬, null/blank 제거)을 반환한다."""
    if df is None or df.empty or column not in df.columns:
        return []
    series = df[column].dropna()
    series = series[series.astype(str).str.strip() != ""]
    return sorted(series.astype(str).unique().tolist())
