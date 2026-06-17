"""data_preprocess 모듈 테스트."""

import pandas as pd

from src.data_preprocess import (
    apply_category_filter,
    classify_url,
    preprocess,
    split_targets,
    unique_values,
)
from src.utils import make_sample_dataframe


def test_classify_pdp_url():
    is_pdp, reason = classify_url("https://www.lge.co.kr/refrigerators/h875gga031")
    assert is_pdp is True
    assert reason == ""


def test_classify_category_url_excluded():
    is_pdp, reason = classify_url("https://www.lge.co.kr/category/refrigerators")
    assert is_pdp is False
    assert "/category/" in reason


def test_classify_mobile_category_url_excluded():
    is_pdp, reason = classify_url("https://www.lge.co.kr/m/category/refrigerators")
    assert is_pdp is False
    assert "/m/category/" in reason


def test_classify_store_url_excluded():
    is_pdp, reason = classify_url("https://www.lge.co.kr/store/event")
    assert is_pdp is False
    assert "/store/" in reason


def test_classify_empty_url_excluded():
    is_pdp, reason = classify_url("")
    assert is_pdp is False
    assert reason == "EMPTY_URL"


def test_classify_non_lge_domain_excluded():
    is_pdp, reason = classify_url("https://www.samsung.com/sec/refrigerators/x")
    assert is_pdp is False
    assert reason == "NON_LGE_DOMAIN"


def test_classify_domain_root_excluded():
    is_pdp, reason = classify_url("https://www.lge.co.kr/")
    assert is_pdp is False
    assert reason == "NO_PRODUCT_PATH"


def test_preprocess_dedup_and_flags():
    df = make_sample_dataframe()
    # 중복 행 추가 (동일 sku + url)
    dup = df.iloc[[0]].copy()
    df = pd.concat([df, dup], ignore_index=True)

    processed = preprocess(df)
    # 중복 제거됨
    assert processed.duplicated(subset=["sku", "clean_page_url"]).sum() == 0
    assert "is_pdp" in processed.columns
    assert "exclude_reason" in processed.columns


def test_split_targets():
    processed = preprocess(make_sample_dataframe())
    targets, excluded = split_targets(processed)
    # 샘플: PDP 2건, 제외 3건
    assert len(targets) == 2
    assert len(excluded) == 3
    assert targets["is_pdp"].all()
    assert not excluded["is_pdp"].any()


def test_apply_category_filter():
    df = make_sample_dataframe()
    filtered = apply_category_filter(df, catg_lvl2_nm=["냉장고"])
    assert (filtered["catg_lvl2_nm"] == "냉장고").all()
    assert len(filtered) >= 1


def test_apply_category_filter_empty_returns_all():
    df = make_sample_dataframe()
    filtered = apply_category_filter(df)
    assert len(filtered) == len(df)


def test_unique_values_sorted_no_blank():
    df = pd.DataFrame({"category": ["b", "a", "", None, "a"]})
    assert unique_values(df, "category") == ["a", "b"]


def test_preprocess_empty():
    out = preprocess(pd.DataFrame())
    assert out.empty
    assert "is_pdp" in out.columns
