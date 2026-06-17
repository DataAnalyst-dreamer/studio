"""LGE.COM PDP 배너 노출 자동 점검 도구 - Streamlit 엔트리포인트.

실행: streamlit run app.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# 패키지 임포트 경로 보장 (`streamlit run app.py` 직접 실행 대응)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.banner_checker import run_banner_check  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data_preprocess import (  # noqa: E402
    apply_category_filter,
    preprocess,
    split_targets,
    unique_values,
)
from src.query_builder import build_query_params  # noqa: E402
from src.redshift_client import RedshiftClient, RedshiftError  # noqa: E402
from src.report_generator import ReportConditions, save_reports, summarize  # noqa: E402
from src.utils import load_sample_dataframe, make_sample_dataframe  # noqa: E402

st.set_page_config(page_title="LGE.COM PDP 배너 점검", page_icon="🔎", layout="wide")

config = load_config()


def _multiselect_filter(df: pd.DataFrame) -> pd.DataFrame:
    """계층형 카테고리 multiselect 4개를 렌더링하고 필터 결과를 반환한다."""
    selected_category = st.multiselect("category", unique_values(df, "category"))
    filtered = apply_category_filter(df, category=selected_category)

    selected_lvl1 = st.multiselect(
        "catg_lvl1_nm", unique_values(filtered, "catg_lvl1_nm")
    )
    filtered = apply_category_filter(
        df, category=selected_category, catg_lvl1_nm=selected_lvl1
    )

    selected_lvl2 = st.multiselect(
        "catg_lvl2_nm", unique_values(filtered, "catg_lvl2_nm")
    )
    filtered = apply_category_filter(
        df,
        category=selected_category,
        catg_lvl1_nm=selected_lvl1,
        catg_lvl2_nm=selected_lvl2,
    )

    selected_lvl3 = st.multiselect(
        "catg_lvl3_nm", unique_values(filtered, "catg_lvl3_nm")
    )
    filtered = apply_category_filter(
        df,
        category=selected_category,
        catg_lvl1_nm=selected_lvl1,
        catg_lvl2_nm=selected_lvl2,
        catg_lvl3_nm=selected_lvl3,
    )

    st.session_state["selected_categories"] = {
        "category": selected_category,
        "catg_lvl1_nm": selected_lvl1,
        "catg_lvl2_nm": selected_lvl2,
        "catg_lvl3_nm": selected_lvl3,
    }
    return filtered


# ---------------------------------------------------------------------------
# 사이드바: 접속/점검 설정
# ---------------------------------------------------------------------------
st.sidebar.header("⚙️ 점검 설정")
banner_path = st.sidebar.text_input("배너 이미지 경로", value=config.banner_image_path)
concurrency = st.sidebar.slider("동시성 (최대 3)", 1, 3, value=config.concurrency)
timeout_ms = st.sidebar.number_input(
    "URL당 Timeout (ms)", min_value=5000, max_value=120000,
    value=config.timeout_ms, step=1000,
)

st.sidebar.divider()
st.sidebar.subheader("Redshift 접속")
if st.sidebar.button("접속 테스트"):
    try:
        RedshiftClient(config.redshift).test_connection()
        st.sidebar.success("Redshift 접속 성공")
    except RedshiftError as exc:
        st.sidebar.error(str(exc))

data_source = st.sidebar.radio(
    "데이터 소스", ["Redshift 조회", "샘플 파일 업로드"], index=0
)

# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
st.title("🔎 LGE.COM PDP 배너 노출 자동 점검")
st.caption(
    "Redshift에서 기간·카테고리로 PDP를 조회하고, Playwright 모바일 렌더링으로 "
    "지정 배너 노출 여부를 점검합니다."
)

# 1. 기간 선택
st.subheader("1. 점검 기간 선택")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("시작일", value=date.today() - timedelta(days=7))
with col2:
    end_date = st.date_input("종료일", value=date.today())

if start_date > end_date:
    st.error("시작일은 종료일보다 늦을 수 없습니다.")
    st.stop()

params = build_query_params(start_date, end_date)
st.caption(f"쿼리 파라미터 → start_date={params['start_date']}, end_date={params['end_date']}")

# 2. 데이터 불러오기
st.subheader("2. 점검 대상 불러오기")
if data_source == "샘플 파일 업로드":
    uploaded = st.file_uploader("CSV/TSV 업로드 (7개 컬럼)", type=["csv", "tsv", "txt"])
    cols = st.columns(2)
    if cols[0].button("업로드 파일 불러오기") and uploaded is not None:
        st.session_state["raw_df"] = load_sample_dataframe(uploaded)
    if cols[1].button("데모 샘플 사용"):
        st.session_state["raw_df"] = make_sample_dataframe()
else:
    if st.button("카테고리 후보 불러오기 (Redshift)"):
        try:
            with st.spinner("Redshift에서 SKU/PDP 후보를 조회 중..."):
                client = RedshiftClient(config.redshift)
                st.session_state["raw_df"] = client.fetch_sku_pages(
                    start_date, end_date
                )
            st.success(f"{len(st.session_state['raw_df'])}건 조회 완료")
        except RedshiftError as exc:
            st.error(str(exc))

# 3. 카테고리 필터 + 미리보기
if "raw_df" in st.session_state:
    raw_df = st.session_state["raw_df"]
    st.info(f"총 조회 행 수: {len(raw_df)}")

    st.subheader("3. 카테고리 계층 선택")
    filtered = _multiselect_filter(raw_df)

    processed = preprocess(filtered)
    targets, excluded = split_targets(processed)

    m1, m2, m3 = st.columns(3)
    m1.metric("선택 행", len(filtered))
    m2.metric("점검 대상 PDP", len(targets))
    m3.metric("제외(EXCLUDED)", len(excluded))

    st.subheader("4. 점검 대상 미리보기")
    st.dataframe(targets, use_container_width=True, height=260)
    with st.expander(f"제외 URL 보기 ({len(excluded)}건)"):
        st.dataframe(excluded, use_container_width=True)

    # 5. 점검 실행
    st.subheader("5. 배너 점검 실행")
    if len(targets) == 0:
        st.warning("점검 대상 PDP가 없습니다. 카테고리 선택을 확인하세요.")
    elif st.button("🚀 배너 점검 실행", type="primary"):
        progress = st.progress(0.0, text="점검 준비 중...")

        def _on_progress(done: int, total: int):
            progress.progress(done / total, text=f"점검 중... {done}/{total}")

        try:
            result_df = run_banner_check(
                targets=targets,
                banner_image_path=banner_path,
                concurrency=concurrency,
                timeout_ms=int(timeout_ms),
                excluded=excluded,
                progress_callback=_on_progress,
            )
            progress.progress(1.0, text="점검 완료")
            st.session_state["result_df"] = result_df
            st.session_state["total_input"] = len(raw_df)
        except Exception as exc:  # noqa: BLE001
            st.error(f"점검 실행 중 오류가 발생했습니다: {exc}")

# 6. 결과
if "result_df" in st.session_state:
    result_df = st.session_state["result_df"]
    st.subheader("6. 점검 결과")

    kpi = summarize(result_df, total_input=st.session_state.get("total_input"))
    k = st.columns(6)
    k[0].metric("총 입력", kpi["total_input"])
    k[1].metric("점검 PDP", kpi["checked"])
    k[2].metric("EXCLUDED", kpi["excluded"])
    k[3].metric("PASS", kpi["passed"], f"{kpi['pass_rate']}%")
    k[4].metric("WARN", kpi["warned"], f"{kpi['warn_rate']}%")
    k[5].metric("FAIL", kpi["failed"], f"{kpi['fail_rate']}%")

    st.dataframe(result_df, use_container_width=True, height=360)

    # 리포트 저장
    sel = st.session_state.get("selected_categories", {})
    cat_text = "; ".join(
        f"{key}={','.join(val)}" for key, val in sel.items() if val
    ) or "전체"
    conditions = ReportConditions(
        period=f"{params['start_date']} ~ {params['end_date']}",
        categories=cat_text,
        concurrency=concurrency,
        timeout_ms=int(timeout_ms),
    )
    paths = save_reports(
        result_df,
        banner_image_path=banner_path,
        output_dir=config.output_dir,
        conditions=conditions,
        total_input=st.session_state.get("total_input"),
    )
    st.success(f"리포트 저장 완료 → {paths['csv']}, {paths['html']}")

    dl1, dl2 = st.columns(2)
    with open(paths["csv"], "rb") as f:
        dl1.download_button(
            "CSV 다운로드", f, file_name=Path(paths["csv"]).name, mime="text/csv"
        )
    with open(paths["html"], "rb") as f:
        dl2.download_button(
            "HTML 리포트 다운로드", f, file_name=Path(paths["html"]).name,
            mime="text/html",
        )
