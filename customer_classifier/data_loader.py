"""
데이터 수집 모듈 — 파일 업로드 또는 DB에서 데이터를 읽어
표준 형식으로 변환합니다.

표준 컬럼:
    inquiry_id  : 문의/리뷰 고유 ID (없으면 자동 부여)
    text        : 본문 (분류 대상)
    written_at  : 작성일 (없을 수 있음)
    product     : 상품명/카테고리 (없을 수 있음)
    data_type   : 'Q&A' 또는 '리뷰' (사용자가 선택)
"""

import uuid
from typing import Optional

import pandas as pd
import streamlit as st

from utils import read_csv_auto, read_excel_auto


STANDARD_COLUMNS = ["inquiry_id", "text", "written_at", "product", "data_type"]

# ─── LGE.COM 사전 정의 쿼리 ────────────────────────────────────────────────

PRESET_QNA_SQL = """\
select distinct
  t1.rvw_inqu_id as q_id
  , coalesce(t2.title,'') || ' ' || coalesce(t1.mak_cntn,'') as q_full_text
  , t1.mak_dt
  , tx.mdl_disp_nm
  , ty.catg_lvl1_nm, ty.catg_lvl2_nm
  , t3.answer_no as a_id
  , datediff(hour, t1.mak_dttm, t1.ansr_dttm) as qa_t_gap
  , regexp_replace(t3.answer_content, '<[^>]+>', ' ') as full_a_cntn
from lge_bi_l1.l1vc_prod_rvw_inqu_l t1
  inner join lge_bi_l0.l0ec_mkt_model_qna_q t2 on t1.rvw_inqu_id = t2.question_no
  left join lge_bi_l0.l0ec_mkt_model_qna_a t3 on t1.rvw_inqu_id = t3.question_no and t3.use_flag = 'Y'
  inner join lge_bi_l1.l1pr_prod_catg_m tx on t1.mdl_id = tx.mdl_id and tx.prod_dv_cd_nm = '{prod_dv}'
  left join lge_bi_l1.l1pr_catg_m ty on tx.catg_id = ty.catg_id
where 1=1
  and t1.mak_dt between '{date_from}' and '{date_to}'
  and t1.del_yn = 0
  and t1.cnts_dv_cd = 'QNA'"""

PRESET_REVIEW_SQL = """\
select distinct
  t1.intg_mbr_id
  , t1.rvw_inqu_id as rvw_id
  , t1.mak_cntn as rvw_cntn
  , t1.rvw_gpa as rating
  , t1.mak_dt, t1.mak_dttm
  , t1.mdl_id, tx.sku, tx.mdl_disp_nm
  , ty.catg_lvl1_nm, ty.catg_lvl2_nm
from lge_bi_l1.l1vc_prod_rvw_inqu_l t1
  inner join lge_bi_l1.l1pr_prod_catg_m tx on t1.mdl_id = tx.mdl_id and tx.prod_dv_cd_nm = '{prod_dv}'
  left join lge_bi_l1.l1pr_catg_m ty on tx.catg_id = ty.catg_id
where 1=1
  and t1.mak_dt between '{date_from}' and '{date_to}'
  and t1.del_yn = 0
  and t1.cnts_dv_cd = 'REVIEW'"""


def normalize_dataframe(
    df: pd.DataFrame,
    col_text: str,
    col_date: Optional[str],
    col_product: Optional[str],
    col_id: Optional[str],
    data_type: str,
) -> pd.DataFrame:
    """원본 DataFrame → 표준 형식 변환"""
    result = pd.DataFrame()

    # 고유 ID
    if col_id and col_id in df.columns:
        result["inquiry_id"] = df[col_id].astype(str)
    else:
        result["inquiry_id"] = [str(uuid.uuid4())[:8] for _ in range(len(df))]

    # 본문
    result["text"] = df[col_text].fillna("").astype(str)

    # 작성일
    if col_date and col_date in df.columns:
        result["written_at"] = df[col_date].astype(str)
    else:
        result["written_at"] = ""

    # 상품/카테고리
    if col_product and col_product in df.columns:
        result["product"] = df[col_product].astype(str)
    else:
        result["product"] = ""

    result["data_type"] = data_type

    # 빈 본문 제거
    result = result[result["text"].str.strip() != ""].reset_index(drop=True)

    return result


def load_from_file(uploaded_file, data_type: str) -> Optional[pd.DataFrame]:
    """파일 업로드 → 컬럼 매핑 UI → 표준 DataFrame 반환"""
    fname = uploaded_file.name.lower()

    if fname.endswith(".csv"):
        df_raw = read_csv_auto(uploaded_file)
    elif fname.endswith((".xlsx", ".xls")):
        df_raw = read_excel_auto(uploaded_file)
    else:
        st.error("지원하지 않는 파일 형식입니다. CSV 또는 Excel(.xlsx) 파일을 올려주세요.")
        return None

    st.markdown("**파일 미리보기 (상위 5행)**")
    st.dataframe(df_raw.head(5), use_container_width=True)

    cols = list(df_raw.columns)
    placeholder = ["(없음)"]

    st.markdown("**컬럼 매핑** — 각 항목에 해당하는 컬럼을 선택하세요.")
    col1, col2 = st.columns(2)
    with col1:
        col_text = st.selectbox(
            "🔤 본문 컬럼 (필수)", cols,
            help="분류할 문의·리뷰 본문이 담긴 컬럼"
        )
        col_date = st.selectbox(
            "📅 작성일 컬럼 (선택)", placeholder + cols,
            help="작성일이 있으면 기간별 추이 차트에 활용됩니다."
        )
    with col2:
        col_product = st.selectbox(
            "📦 상품·카테고리 컬럼 (선택)", placeholder + cols,
            help="상품명 또는 카테고리 컬럼 (없으면 건너뜀)"
        )
        col_id = st.selectbox(
            "🔑 고유ID 컬럼 (선택)", placeholder + cols,
            help="문의/리뷰 고유 번호 컬럼 (없으면 자동 부여)"
        )

    col_date = None if col_date == "(없음)" else col_date
    col_product = None if col_product == "(없음)" else col_product
    col_id = None if col_id == "(없음)" else col_id

    return normalize_dataframe(df_raw, col_text, col_date, col_product, col_id, data_type)


def load_from_db(conn, data_type: str) -> Optional[pd.DataFrame]:
    """DB 연결 → 테이블·컬럼 선택 UI → 표준 DataFrame 반환"""
    import db_connector as dbc

    st.markdown("**DB 탐색 — 데이터를 불러올 방법을 선택하세요**")

    tab_preset, tab_builder, tab_custom = st.tabs(
        ["⭐ LGE.COM 사전 정의 쿼리", "📋 테이블 선택", "✏️ SQL 직접 입력"]
    )

    # ── 탭 0: 사전 정의 쿼리 ──────────────────────────────────────────────
    with tab_preset:
        st.markdown(
            "LGE.COM Q&A 및 리뷰 데이터에 최적화된 쿼리가 미리 준비되어 있습니다. "
            "날짜 범위와 최대 행 수만 설정하고 실행하세요."
        )

        preset_type = st.radio(
            "데이터 유형", ["Q&A (고객 문의)", "리뷰 (상품 후기)"],
            horizontal=True, key="preset_type"
        )

        sale_type = st.radio(
            "판매 유형", ["일시불", "구독"],
            horizontal=True, key="preset_sale_type",
            help="일시불은 일반제품, 구독은 가전 구독(prod_dv_cd_nm)으로 조회합니다.",
        )
        # 화면 선택값 → prod_dv_cd_nm 실제 코드값 매핑
        PROD_DV_MAP = {"일시불": "일반제품", "구독": "가전 구독"}
        prod_dv = PROD_DV_MAP[sale_type]

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            p_from = st.text_input("시작일 (YYYYMMDD)", value="20250101", key="p_from")
        with col_d2:
            p_to = st.text_input("종료일 (YYYYMMDD)", value="20260430", key="p_to")

        is_qna = preset_type.startswith("Q&A")
        raw_sql = (PRESET_QNA_SQL if is_qna else PRESET_REVIEW_SQL).format(
            date_from=p_from.strip(), date_to=p_to.strip(), prod_dv=prod_dv
        )
        # 분류에 사용할 본문 컬럼 / ID 컬럼 / 날짜 컬럼
        text_col   = "q_full_text" if is_qna else "rvw_cntn"
        id_col     = "q_id"        if is_qna else "rvw_id"
        dtype_val  = "Q&A"         if is_qna else "리뷰"

        with st.expander("🔍 실행될 SQL 미리보기"):
            st.code(raw_sql, language="sql")

        preset_limit = st.number_input(
            "최대 행 수", min_value=100, max_value=100000, value=10000, step=1000,
            key="preset_limit",
            help="처음에는 1,000~5,000건으로 테스트하고, 샘플 품질 확인 후 늘리세요."
        )

        if st.button("📥 쿼리 실행", key="preset_fetch", type="primary"):
            with st.spinner("데이터를 불러오는 중..."):
                df_raw = dbc.execute_custom_sql(conn, raw_sql, int(preset_limit))

            if len(df_raw) == 0:
                st.warning("조회 결과가 0건입니다. 날짜 범위 또는 조건을 확인해주세요.")
            else:
                st.success(f"✅ {len(df_raw):,}건 불러왔습니다.")
                st.markdown("**미리보기 (상위 5행)**")
                st.dataframe(df_raw.head(5), use_container_width=True)

                if text_col not in df_raw.columns:
                    st.error(
                        f"'{text_col}' 컬럼을 찾을 수 없습니다. "
                        "SQL이 정상 실행됐는지 확인하거나 'SQL 직접 입력' 탭을 이용하세요."
                    )
                else:
                    return normalize_dataframe(
                        df_raw, text_col, "mak_dt", "mdl_disp_nm", id_col, dtype_val
                    )

    # ── 이하 기존 탭들 ───────────────────────────────────────────────────
    schemas = dbc.list_schemas(conn)

    with tab_builder:
        if not schemas:
            st.warning(
                "스키마 목록을 자동으로 불러오지 못했습니다.\n\n"
                "**원인:** 계정 권한 또는 Redshift 뷰 접근 제한\n\n"
                "**해결 방법:** 'SQL 직접 입력' 탭 또는 '⭐ LGE.COM 사전 정의 쿼리' 탭을 사용하세요."
            )
        else:
            pass  # 아래에서 처리

        col_a, col_b = st.columns(2)
        with col_a:
            schema = st.selectbox("스키마 선택", schemas if schemas else ["(없음)"])
        tables = dbc.list_tables(conn, schema)
        if not tables:
            st.warning(f"'{schema}' 스키마에 테이블이 없습니다.")
            return None
        with col_b:
            table = st.selectbox("테이블 선택", tables)

        columns = dbc.list_columns(conn, schema, table)
        placeholder = ["(없음)"]

        st.markdown("**컬럼 매핑**")
        c1, c2 = st.columns(2)
        with c1:
            col_text = st.selectbox("🔤 본문 컬럼 (필수)", columns, key="db_text")
            col_date = st.selectbox("📅 작성일 컬럼 (선택)", placeholder + columns, key="db_date")
        with c2:
            col_product = st.selectbox("📦 상품·카테고리 컬럼 (선택)", placeholder + columns, key="db_product")
            col_id = st.selectbox("🔑 고유ID 컬럼 (선택)", placeholder + columns, key="db_id")

        col_date_v = None if col_date == "(없음)" else col_date
        col_product_v = None if col_product == "(없음)" else col_product
        col_id_v = None if col_id == "(없음)" else col_id

        date_c1, date_c2 = st.columns(2)
        with date_c1:
            date_from = st.text_input("시작일 (예: 2024-01-01)", value="", key="db_from")
        with date_c2:
            date_to = st.text_input("종료일 (예: 2024-12-31)", value="", key="db_to")
        limit = st.number_input("최대 불러올 행 수", min_value=100, max_value=100000, value=10000, step=1000)

        if st.button("📥 데이터 불러오기", key="db_fetch"):
            with st.spinner("데이터를 불러오는 중..."):
                df_raw = dbc.fetch_data(
                    conn, schema, table, col_text,
                    col_date_v, col_product_v, col_id_v,
                    date_from or None, date_to or None, int(limit),
                )
            st.success(f"{len(df_raw):,}건 불러왔습니다.")
            st.dataframe(df_raw.head(5), use_container_width=True)
            return normalize_dataframe(df_raw, col_text, col_date_v, col_product_v, col_id_v, data_type)

    with tab_custom:
        st.markdown(
            "직접 SQL을 입력해 특정 기간·카테고리 데이터만 추출할 수 있습니다. "
            "**SELECT 문만** 사용 가능합니다."
        )
        custom_sql = st.text_area(
            "SQL 입력", height=120,
            placeholder="SELECT inquiry_id, content, created_at, product_name FROM schema.table WHERE created_at >= '2024-01-01' LIMIT 5000",
            key="db_custom_sql"
        )
        limit_custom = st.number_input("최대 행 수 (SQL에 LIMIT 없을 때 자동 적용)", min_value=100, max_value=100000, value=10000, step=1000, key="limit_custom")

        if st.button("📥 SQL 실행", key="db_custom_fetch"):
            if not custom_sql.strip():
                st.warning("SQL을 입력해주세요.")
                return None
            with st.spinner("SQL 실행 중..."):
                df_raw = dbc.execute_custom_sql(conn, custom_sql, int(limit_custom))
            st.success(f"{len(df_raw):,}건 불러왔습니다.")
            st.dataframe(df_raw.head(5), use_container_width=True)

            cols = list(df_raw.columns)
            placeholder = ["(없음)"]
            c1, c2 = st.columns(2)
            with c1:
                col_text2 = st.selectbox("🔤 본문 컬럼 (필수)", cols, key="cust_text")
                col_date2 = st.selectbox("📅 작성일 컬럼 (선택)", placeholder + cols, key="cust_date")
            with c2:
                col_product2 = st.selectbox("📦 상품·카테고리 컬럼 (선택)", placeholder + cols, key="cust_product")
                col_id2 = st.selectbox("🔑 고유ID 컬럼 (선택)", placeholder + cols, key="cust_id")

            return normalize_dataframe(
                df_raw, col_text2,
                None if col_date2 == "(없음)" else col_date2,
                None if col_product2 == "(없음)" else col_product2,
                None if col_id2 == "(없음)" else col_id2,
                data_type,
            )

    return None
