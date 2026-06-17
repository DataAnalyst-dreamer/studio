"""banner_checker / report_generator 테스트.

Playwright 실행 없이 순수 판정/집계 로직만 검증한다.
"""

import pandas as pd

from src.banner_checker import (
    STATUS_EXCLUDED,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    classify_banner,
)
from src.report_generator import (
    ReportConditions,
    category_summary,
    render_html,
    save_reports,
    summarize,
)


def test_classify_banner_pass():
    status, reason = classify_banner(True, True, 656, 220)
    assert status == STATUS_PASS
    assert reason == "BANNER_VISIBLE_AND_LOADED"


def test_classify_banner_warn_not_visible():
    status, reason = classify_banner(True, False, 656, 220)
    assert status == STATUS_WARN
    assert "NOT_VISIBLE" in reason


def test_classify_banner_warn_not_loaded():
    status, reason = classify_banner(True, True, 0, 0)
    assert status == STATUS_WARN
    assert "NOT_LOADED" in reason


def test_classify_banner_fail_missing():
    status, reason = classify_banner(False, False, 0, 0)
    assert status == STATUS_FAIL
    assert reason == "BANNER_DOM_NOT_FOUND"


def _sample_results() -> pd.DataFrame:
    rows = [
        {"status": STATUS_PASS, "category": "12인용", "catg_lvl2_nm": "냉장고",
         "sku": "A", "clean_page_url": "u1", "is_visible": True,
         "natural_width": 656, "natural_height": 220, "reason": "ok",
         "http_status": 200, "elapsed_ms": 100, "error_message": ""},
        {"status": STATUS_WARN, "category": "12인용", "catg_lvl2_nm": "냉장고",
         "sku": "B", "clean_page_url": "u2", "is_visible": False,
         "natural_width": 0, "natural_height": 0, "reason": "warn",
         "http_status": 200, "elapsed_ms": 120, "error_message": ""},
        {"status": STATUS_FAIL, "category": "14인용", "catg_lvl2_nm": "냉장고",
         "sku": "C", "clean_page_url": "u3", "is_visible": False,
         "natural_width": 0, "natural_height": 0, "reason": "fail",
         "http_status": 404, "elapsed_ms": 90, "error_message": "x"},
        {"status": STATUS_EXCLUDED, "category": "스토어", "catg_lvl2_nm": "스토어",
         "sku": "D", "clean_page_url": "u4", "is_visible": False,
         "natural_width": 0, "natural_height": 0, "reason": "NON_PDP",
         "http_status": None, "elapsed_ms": 0, "error_message": ""},
    ]
    return pd.DataFrame(rows)


def test_summarize_counts_and_rates():
    kpi = summarize(_sample_results())
    assert kpi["passed"] == 1
    assert kpi["warned"] == 1
    assert kpi["failed"] == 1
    assert kpi["excluded"] == 1
    assert kpi["checked"] == 3
    assert kpi["pass_rate"] == round(1 / 3 * 100, 1)


def test_category_summary():
    rows = category_summary(_sample_results())
    assert len(rows) >= 1
    total = sum(r["total"] for r in rows)
    assert total == 4


def test_render_html_contains_sections():
    html = render_html(
        _sample_results(),
        banner_image_path="/kr/x/banner.png",
        conditions=ReportConditions(period="20260601 ~ 20260607"),
    )
    assert "요약 KPI" in html
    assert "FAIL / WARN 우선 목록" in html
    assert "/kr/x/banner.png" in html
    assert "20260601 ~ 20260607" in html


def test_save_reports(tmp_path):
    paths = save_reports(
        _sample_results(),
        banner_image_path="/kr/x/banner.png",
        output_dir=str(tmp_path),
        conditions=ReportConditions(period="p"),
        timestamp="20260101_000000",
    )
    import os

    assert os.path.exists(paths["csv"])
    assert os.path.exists(paths["html"])
    assert paths["csv"].endswith("banner_check_20260101_000000.csv")


def test_summarize_empty():
    kpi = summarize(pd.DataFrame())
    assert kpi["checked"] == 0
    assert kpi["pass_rate"] == 0.0
