"""CSV/HTML 리포트 생성 모듈.

점검 결과 DataFrame을 받아 요약 KPI, 카테고리별 집계, 상세 결과,
FAIL/WARN 우선 목록을 포함한 HTML 리포트와 CSV를 outputs 폴더에 저장한다
(PRD 11 / FR-007).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from jinja2 import Environment, BaseLoader, select_autoescape

from .banner_checker import (
    STATUS_EXCLUDED,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
)

_HTML_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LGE.COM PDP 배너 노출 점검 리포트</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",Roboto,Arial,sans-serif;margin:0;background:#f7f8fa;color:#202124;line-height:1.6;}
  .wrap{max-width:1180px;margin:0 auto;padding:32px 24px 64px;}
  header{background:linear-gradient(135deg,#a50034,#6f0022);color:#fff;border-radius:18px;padding:28px 32px;margin-bottom:24px;}
  header h1{margin:0 0 8px;font-size:24px;}
  header p{margin:2px 0;color:rgba(255,255,255,.9);font-size:14px;}
  h2{font-size:19px;border-left:5px solid #a50034;padding-left:12px;margin:30px 0 12px;}
  .cards{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;}
  .card{background:#fff;border:1px solid #dadce0;border-radius:12px;padding:14px;text-align:center;}
  .card .label{font-size:12px;color:#5f6368;}
  .card .value{font-size:22px;font-weight:700;margin-top:4px;}
  .card .pct{font-size:12px;color:#5f6368;}
  table{width:100%;border-collapse:collapse;background:#fff;font-size:13px;margin:12px 0 24px;border-radius:10px;overflow:hidden;}
  th,td{border:1px solid #e3e3e3;padding:8px 10px;text-align:left;vertical-align:top;}
  th{background:#f1f3f4;font-weight:700;}
  .badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700;}
  .PASS{background:#e6f4ea;color:#137333;}
  .WARN{background:#fef7e0;color:#b06000;}
  .FAIL{background:#fce8e6;color:#b3261e;}
  .EXCLUDED{background:#eceff1;color:#5f6368;}
  .small{color:#5f6368;font-size:13px;}
  .url{word-break:break-all;max-width:380px;}
  .cond td{font-size:13px;}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>LGE.COM PDP 배너 노출 점검 리포트</h1>
    <p>생성 시각: {{ generated_at }}</p>
    <p>배너 경로: {{ banner_image_path }}</p>
  </header>

  <h2>점검 조건</h2>
  <table class="cond">
    <tr><th>점검 기간</th><td>{{ conditions.period }}</td></tr>
    <tr><th>선택 카테고리</th><td>{{ conditions.categories }}</td></tr>
    <tr><th>배너 경로</th><td>{{ banner_image_path }}</td></tr>
    <tr><th>Viewport</th><td>{{ conditions.viewport }}</td></tr>
    <tr><th>동시성 / Timeout</th><td>{{ conditions.concurrency }} / {{ conditions.timeout_ms }}ms</td></tr>
  </table>

  <h2>요약 KPI</h2>
  <div class="cards">
    <div class="card"><div class="label">총 입력 행</div><div class="value">{{ kpi.total_input }}</div></div>
    <div class="card"><div class="label">점검 대상 PDP</div><div class="value">{{ kpi.checked }}</div></div>
    <div class="card"><div class="label">제외 URL</div><div class="value">{{ kpi.excluded }}</div></div>
    <div class="card"><div class="label">PASS</div><div class="value" style="color:#137333">{{ kpi.passed }}</div><div class="pct">{{ kpi.pass_rate }}%</div></div>
    <div class="card"><div class="label">WARN</div><div class="value" style="color:#b06000">{{ kpi.warned }}</div><div class="pct">{{ kpi.warn_rate }}%</div></div>
    <div class="card"><div class="label">FAIL</div><div class="value" style="color:#b3261e">{{ kpi.failed }}</div><div class="pct">{{ kpi.fail_rate }}%</div></div>
  </div>

  <h2>카테고리별 집계</h2>
  <table>
    <thead><tr><th>category</th><th>catg_lvl2_nm</th><th>PASS</th><th>WARN</th><th>FAIL</th><th>EXCLUDED</th><th>합계</th></tr></thead>
    <tbody>
    {% for row in category_summary %}
      <tr>
        <td>{{ row.category }}</td><td>{{ row.catg_lvl2_nm }}</td>
        <td>{{ row.PASS }}</td><td>{{ row.WARN }}</td><td>{{ row.FAIL }}</td>
        <td>{{ row.EXCLUDED }}</td><td>{{ row.total }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <h2>FAIL / WARN 우선 목록</h2>
  {% if priority_rows %}
  <table>
    <thead><tr><th>상태</th><th>sku</th><th>category</th><th>URL</th><th>사유</th><th>visible</th><th>WxH</th><th>오류</th></tr></thead>
    <tbody>
    {% for r in priority_rows %}
      <tr>
        <td><span class="badge {{ r.status }}">{{ r.status }}</span></td>
        <td>{{ r.sku }}</td>
        <td>{{ r.category }}</td>
        <td class="url">{{ r.clean_page_url }}</td>
        <td>{{ r.reason }}</td>
        <td>{{ r.is_visible }}</td>
        <td>{{ r.natural_width }}x{{ r.natural_height }}</td>
        <td class="small">{{ r.error_message }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="small">FAIL/WARN 항목이 없습니다.</p>
  {% endif %}

  <h2>상세 결과 ({{ detail_rows|length }}건)</h2>
  <table>
    <thead><tr><th>상태</th><th>sku</th><th>category</th><th>lvl2</th><th>URL</th><th>사유</th><th>HTTP</th><th>visible</th><th>WxH</th><th>ms</th></tr></thead>
    <tbody>
    {% for r in detail_rows %}
      <tr>
        <td><span class="badge {{ r.status }}">{{ r.status }}</span></td>
        <td>{{ r.sku }}</td>
        <td>{{ r.category }}</td>
        <td>{{ r.catg_lvl2_nm }}</td>
        <td class="url">{{ r.clean_page_url }}</td>
        <td>{{ r.reason }}</td>
        <td>{{ r.http_status }}</td>
        <td>{{ r.is_visible }}</td>
        <td>{{ r.natural_width }}x{{ r.natural_height }}</td>
        <td>{{ r.elapsed_ms }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <p class="small">© LGE.COM 내부 QA 자동화 도구 · 본 리포트는 모바일 viewport 렌더링 기준입니다.</p>
</div>
</body>
</html>
"""


@dataclass
class ReportConditions:
    """리포트에 기록할 점검 조건."""

    period: str = ""
    categories: str = ""
    viewport: str = "390x844 (isMobile)"
    concurrency: int = 3
    timeout_ms: int = 30000


def _rate(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole * 100, 1)


def summarize(result_df: pd.DataFrame, total_input: Optional[int] = None) -> dict:
    """요약 KPI를 계산한다(PRD 11.1)."""
    if result_df is None or result_df.empty:
        return {
            "total_input": total_input or 0,
            "checked": 0,
            "excluded": 0,
            "passed": 0,
            "warned": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "warn_rate": 0.0,
            "fail_rate": 0.0,
        }

    counts = result_df["status"].value_counts().to_dict()
    passed = int(counts.get(STATUS_PASS, 0))
    warned = int(counts.get(STATUS_WARN, 0))
    failed = int(counts.get(STATUS_FAIL, 0))
    excluded = int(counts.get(STATUS_EXCLUDED, 0))
    checked = passed + warned + failed

    return {
        "total_input": total_input if total_input is not None else len(result_df),
        "checked": checked,
        "excluded": excluded,
        "passed": passed,
        "warned": warned,
        "failed": failed,
        "pass_rate": _rate(passed, checked),
        "warn_rate": _rate(warned, checked),
        "fail_rate": _rate(failed, checked),
    }


def category_summary(result_df: pd.DataFrame) -> list[dict]:
    """카테고리(category, catg_lvl2_nm)별 상태 집계를 생성한다."""
    if result_df is None or result_df.empty:
        return []
    df = result_df.copy()
    df["category"] = df["category"].fillna("(미분류)")
    df["catg_lvl2_nm"] = df["catg_lvl2_nm"].fillna("")
    grouped = (
        df.groupby(["category", "catg_lvl2_nm", "status"])
        .size()
        .unstack(fill_value=0)
    )
    rows = []
    for (category, lvl2), series in grouped.iterrows():
        row = {
            "category": category,
            "catg_lvl2_nm": lvl2,
            "PASS": int(series.get(STATUS_PASS, 0)),
            "WARN": int(series.get(STATUS_WARN, 0)),
            "FAIL": int(series.get(STATUS_FAIL, 0)),
            "EXCLUDED": int(series.get(STATUS_EXCLUDED, 0)),
        }
        row["total"] = row["PASS"] + row["WARN"] + row["FAIL"] + row["EXCLUDED"]
        rows.append(row)
    rows.sort(key=lambda r: (-r["FAIL"], -r["WARN"], r["category"]))
    return rows


def render_html(
    result_df: pd.DataFrame,
    banner_image_path: str,
    conditions: Optional[ReportConditions] = None,
    total_input: Optional[int] = None,
) -> str:
    """HTML 리포트 문자열을 생성한다."""
    conditions = conditions or ReportConditions()
    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.from_string(_HTML_TEMPLATE)

    kpi = summarize(result_df, total_input=total_input)
    detail_rows = (
        result_df.fillna("").to_dict("records")
        if result_df is not None and not result_df.empty
        else []
    )
    priority_rows = [
        r for r in detail_rows if r.get("status") in (STATUS_FAIL, STATUS_WARN)
    ]

    return template.render(
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        banner_image_path=banner_image_path,
        conditions={
            "period": conditions.period,
            "categories": conditions.categories,
            "viewport": conditions.viewport,
            "concurrency": conditions.concurrency,
            "timeout_ms": conditions.timeout_ms,
        },
        kpi=kpi,
        category_summary=category_summary(result_df),
        priority_rows=priority_rows,
        detail_rows=detail_rows,
    )


def save_reports(
    result_df: pd.DataFrame,
    banner_image_path: str,
    output_dir: str = "outputs",
    conditions: Optional[ReportConditions] = None,
    total_input: Optional[int] = None,
    timestamp: Optional[str] = None,
) -> dict[str, str]:
    """CSV와 HTML 리포트를 저장하고 경로를 반환한다(PRD 8.7 / FR-007).

    파일명: banner_check_YYYYMMDD_HHMMSS.{csv,html}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = out / f"banner_check_{ts}.csv"
    html_path = out / f"banner_check_{ts}.html"

    if result_df is None:
        result_df = pd.DataFrame()

    # CSV: 한글 깨짐 방지를 위해 utf-8-sig
    result_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    html = render_html(
        result_df,
        banner_image_path=banner_image_path,
        conditions=conditions,
        total_input=total_input,
    )
    html_path.write_text(html, encoding="utf-8")

    return {"csv": str(csv_path), "html": str(html_path)}
