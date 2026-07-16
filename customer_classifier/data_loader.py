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

# ── 구매 여정 연계 Q&A 쿼리 ──────────────────────────────────────────────
# Q&A 작성 전/후의 장바구니·구매 행동을 ±2개월 창으로 붙여, 문의가 고객 여정의
# 어느 단계(구매전/검토중/구매후/행동없음)에서 나왔는지 판정할 수 있게 한다.
#
# ★ 날짜 파라미터가 2벌인 이유:
#   {date_from}/{date_to}  : Q&A 작성 기간 (사용자 입력 그대로)
#   {ctx_from}/{ctx_to}    : 행동(장바구니·주문) 조회 기간 = Q&A 기간 ±2개월 자동 확장
#   행동 데이터를 Q&A와 같은 기간으로만 조회하면 ±2개월 조인 창을 커버하지 못해
#   대부분 '행동없음'으로 잘못 판정된다.
#
# 개인정보 최소화: intg_mbr_id·주문번호는 조인에만 쓰고 최종 출력에서 제외한다.
PRESET_QNA_JOURNEY_SQL = r"""
with cart as (
-- 한 사람당 한 제품의 장바구니 담기는 최초 시점 1건으로 요약 (전/후 '시점' 정의가 상대적이기 때문)
select t1.mbr_no as intg_mbr_id
    , t1.goods_no as sku
    , t21.mdl_id
    , 'online_d2c' as chnl_type
    , min(t1.reg_dtime) as cart_dttm
from lge_bi_l0.l0ec_mb_cart t1
    left join lge_bi_l1.l1pr_prod_catg_m t21 on t1.goods_no = t21.sku and t21.prod_dv_cd_nm = '{prod_dv}'
where 1=1
    and to_char(t1.reg_dtime, 'YYYYMMDD') between '{ctx_from}' and '{ctx_to}'
    and t1.mbr_no <> 'NOMEMBER' -- 비회원 장바구니 제외
    and t1.goods_no !~ '^G\\d+$' -- 리빙 제외
group by all
)
, ordr_pre1 as (
-- 닷컴+타채널 구매 통합용 cust_no 기준표 (Q&A 작성자는 LG전자회원)
select distinct ord.ordr_no, ord.cust_no, obs.src_cust_no
from lge_bi_l0.l0ed_l1cdp_ordr_cust_mapg_r ord
    inner join (select distinct cust_no, src_cust_no
                    from lge_bi_l0.l0ed_l1cdp_cust_mapg_r
                    where src_chnl_nm = 'LG전자회원고객'
                    ) obs on ord.cust_no = obs.cust_no
where buy_hld_dv_cd = 'BUY'
)
, ordr_pre2 as (
-- 닷컴+타채널 구매 내역 (Q&A 기간 ±2개월)
select distinct t2.cust_no, t2.src_cust_no as intg_mbr_id
    , to_timestamp(t1.ordr_dt||t1.ordr_hhmmss, 'YYYYMMDDHH24MISS')::timestamp as ordr_dttm
    , t1.ordr_no
    , case when lgebst_buy_chnl_nm = 'LG전자 Mall' then 'online_d2c'
             when ordr_sys_nm in ('CSMS(OBS렌탈)', 'GERP(OBS)', 'GERP(OBS케어십)') then 'online_d2c'
             when lgebst_buy_chnl_nm in ('BEST SHOP(J)', 'BS(J)', 'BEST SHOP(H)', '홈플러스(H)', '백화점(H)', '하이프라자 본사', 'HiP 중부담당지점') then 'offline'
            when lgebst_buy_chnl_nm in ('하이마트', '전자랜드', '이마트', '홈플러스', '할인점(LGE)', '하이마트본사', '전자랜드본사', 'E-MART') then 'offline'
            when lgebst_buy_chnl_nm in ('B2B_납품전문점', 'B2B_시스템전문점', '커머셜납품전문점', '시스템전문점') then 'b2b'
            when lgebst_buy_chnl_nm in ('LG BEST SHOP mall', 'LG나라', '온라인', '인터넷/홈쇼핑', '전문유통전문점', '판매특약점') then 'online_else'
            when lgebst_buy_chnl_nm in ('렌탈전문점') then 'rental'
            else 'etc'
             end as chnl_type
    , t1.mdl_cd as sku
    , t21.mdl_id
from lge_bi_l0.l0ed_l1cdp_buy_ordr_l t1
    inner join ordr_pre1 t2 on t1.ordr_no = t2.ordr_no
    left join lge_bi_l1.l1pr_prod_catg_m t21 on t1.mdl_cd = t21.sku and t21.prod_dv_cd_nm = '{prod_dv}'
where 1=1
    and ordr_dt between '{ctx_from}' and '{ctx_to}'
    and t1.buy_qt >= 0 -- 세트 대표상품 qt=0 대응 (취반품은 -1)
    and length(ordr_lin_no) - length(replace(ordr_lin_no, '.', '')) = 1
group by all
)
, ordr as (
-- 한 사람당 한 제품을 채널당 한 번(최초 시점)으로 요약
select distinct intg_mbr_id, sku, mdl_id, chnl_type
    , first_value(ordr_dttm) over(partition by intg_mbr_id, mdl_id, chnl_type order by ordr_dttm rows between unbounded preceding and unbounded following) as ordr_dttm
from ordr_pre2
)
, pre as (
select distinct t1.rvw_inqu_id as q_id
    , '제목 : '||coalesce(t2.title,'')||' & 내용 : '||coalesce(t1.mak_cntn,'') as full_q_cntn
    , t1.intg_mbr_id, t1.mdl_id, t1.mak_dt, t1.mak_dttm, t1.ansr_dttm
    , datediff(hour, t1.mak_dttm, t1.ansr_dttm) as qa_t_gap
    , t3.answer_no as a_id, regexp_replace(t3.answer_content, '<[^>]+>', ' ') as full_a_cntn
from lge_bi_l1.l1vc_prod_rvw_inqu_l t1
    inner join lge_bi_l0.l0ec_mkt_model_qna_q t2 on t1.rvw_inqu_id = t2.question_no
    left join lge_bi_l0.l0ec_mkt_model_qna_a t3 on t1.rvw_inqu_id = t3.question_no and t3.use_flag = 'Y'
where 1=1
    and t1.mak_dt between '{date_from}' and '{date_to}'
    and t1.del_yn = 0
    and t1.cnts_dv_cd = 'QNA'
)
select
    -- 제품/카테고리
    tx.mdl_disp_nm, ty.catg_lvl1_nm, ty.catg_lvl2_nm
    -- Q&A 본문·답변
    , ta.q_id, ta.mak_dt, ta.mak_dttm, ta.full_q_cntn
    , ta.a_id, ta.qa_t_gap
    , case when tc.cart_dttm >= ta.ansr_dttm then datediff(hour, ta.ansr_dttm, tc.cart_dttm) end as ac_t_gap -- 답변→장바구니 리드타임
    , case when tb.ordr_dttm >= ta.ansr_dttm then datediff(hour, ta.ansr_dttm, tb.ordr_dttm) end as ao_t_gap -- 답변→주문 리드타임
    , case when replace(ta.full_a_cntn, ' ', '') !~'답변이지연되어'
            and replace(ta.full_a_cntn, ' ', '') ~'죄송합니다|죄송하게도|안내가어렵습니다|개인정보를수집하지않아|도움드리지못해' then 'fail'
            end as a_fail_yn
    , ta.full_a_cntn
    -- 행동 시점 (cart_dttm_re는 아래 여정 플래그가 참조하므로 먼저 정의)
    , case when tb.chnl_type = 'online_d2c' then tc.cart_dttm end as cart_dttm_re
    , tb.ordr_dttm
    , tb.chnl_type as ord_chnl
    -- 여정 플래그
    , case when cart_dttm_re is null and tb.ordr_dttm is null then 1 else 0 end as just_ask -- 행동없음
    , case when ta.mak_dttm between add_months(cart_dttm_re, -2) and cart_dttm_re then 1 -- 장바구니 2개월 전 문의
           when ta.mak_dttm between add_months(tb.ordr_dttm, -2) and tb.ordr_dttm       -- 구매 2개월 전 문의 (닷컴)
                  and (ta.mak_dttm < cart_dttm_re or cart_dttm_re is null)
                  and tb.chnl_type = 'online_d2c'                                               then 1 else 0 end as before_d2c
    , case when ta.mak_dttm between add_months(tb.ordr_dttm, -2) and tb.ordr_dttm -- 구매 2개월 전 문의 (타채널)
                  and tb.chnl_type <> 'online_d2c'                                                then 1 else 0 end as before_else
    , case when ta.mak_dttm between cart_dttm_re    and add_months(cart_dttm_re, 2)
                                and (ta.mak_dttm < tb.ordr_dttm or tb.ordr_dttm is null) then 1 else 0 end as browse_d2c -- 장바구니 후 문의
    , case when ta.mak_dttm between tb.ordr_dttm    and add_months(tb.ordr_dttm, 2)
                                                                and tb.chnl_type = 'online_d2c' then 1 else 0 end as after_d2c -- 구매 후 문의 (닷컴)
    , case when ta.mak_dttm between tb.ordr_dttm    and add_months(tb.ordr_dttm, 2)
                                                                and tb.chnl_type <> 'online_d2c' then 1 else 0 end as after_else -- 구매 후 문의 (타채널)
from pre ta
    left join cart tc on ta.intg_mbr_id = tc.intg_mbr_id and ta.mdl_id = tc.mdl_id and ta.mak_dttm between add_months(tc.cart_dttm, -2) and add_months(tc.cart_dttm, +2)
    left join ordr tb on ta.intg_mbr_id = tb.intg_mbr_id and ta.mdl_id = tb.mdl_id and ta.mak_dttm between add_months(tb.ordr_dttm, -2) and add_months(tb.ordr_dttm, +2)
    left join lge_bi_l1.l1pr_prod_catg_m tx on ta.mdl_id = tx.mdl_id and tx.prod_dv_cd_nm = '{prod_dv}'
    left join lge_bi_l1.l1pr_catg_m ty on tx.catg_id = ty.catg_id
order by ta.q_id, ta.mak_dttm"""


def shift_yyyymmdd(d: str, months: int) -> str:
    """YYYYMMDD 문자열을 ±N개월 이동 (월말 초과 시 해당 월 말일로 보정)"""
    import calendar

    y, m, day = int(d[:4]), int(d[4:6]), int(d[6:8])
    idx = y * 12 + (m - 1) + months
    y2, m2 = idx // 12, idx % 12 + 1
    day = min(day, calendar.monthrange(y2, m2)[1])
    return f"{y2:04d}{m2:02d}{day:02d}"


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
    extra_cols: Optional[list] = None,
) -> pd.DataFrame:
    """원본 DataFrame → 표준 형식 변환.
    extra_cols에 지정된 컬럼은 존재할 경우 표준 컬럼 뒤에 그대로 붙는다
    (여정 분석 등 부가 지표를 분류 결과까지 끌고 가기 위함)."""
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

    # 부가 분석 컬럼 통과
    if extra_cols:
        for c in extra_cols:
            if c in df.columns and c not in result.columns:
                result[c] = df[c].values

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

        is_qna = preset_type.startswith("Q&A")

        journey_mode = False
        if is_qna:
            journey_mode = st.checkbox(
                "🧭 구매 여정 연계 (문의 전/후 장바구니·구매 행동 분석)",
                value=False, key="preset_journey",
                help="문의가 고객 여정의 어느 단계(구매전/검토중/구매후/행동없음)에서 "
                     "나왔는지와 문의 후 구매 전환 여부를 함께 추출합니다. "
                     "조인이 많아 조회 시간이 더 걸립니다.",
            )

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            p_from = st.text_input("시작일 (YYYYMMDD)", value="20250101", key="p_from")
        with col_d2:
            p_to = st.text_input("종료일 (YYYYMMDD)", value="20260430", key="p_to")

        if journey_mode:
            # 행동(장바구니·주문) 데이터는 Q&A 기간 ±2개월로 넓혀 조회해야
            # 전/후 판정 조인 창(±2개월)이 정상 동작한다.
            ctx_from = shift_yyyymmdd(p_from.strip(), -2)
            ctx_to   = shift_yyyymmdd(p_to.strip(), +2)
            raw_sql = PRESET_QNA_JOURNEY_SQL.format(
                date_from=p_from.strip(), date_to=p_to.strip(),
                ctx_from=ctx_from, ctx_to=ctx_to, prod_dv=prod_dv,
            )
            st.caption(f"행동 데이터 조회 기간: {ctx_from} ~ {ctx_to} (Q&A 기간 ±2개월 자동 확장)")
        else:
            raw_sql = (PRESET_QNA_SQL if is_qna else PRESET_REVIEW_SQL).format(
                date_from=p_from.strip(), date_to=p_to.strip(), prod_dv=prod_dv
            )
        # 분류에 사용할 본문 컬럼 / ID 컬럼 / 날짜 컬럼
        text_col   = ("full_q_cntn" if journey_mode else "q_full_text") if is_qna else "rvw_cntn"
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
                elif journey_mode:
                    import journey as jn

                    df_j = jn.prepare_journey_dataframe(df_raw)
                    n_dup = len(df_raw) - len(df_j)
                    if n_dup > 0:
                        st.caption(f"중복 행동 조인 {n_dup:,}행을 문의당 1건으로 병합했습니다.")
                    st.markdown("**여정 단계 분포**")
                    st.dataframe(jn.journey_summary(df_j), use_container_width=True, hide_index=True)
                    return normalize_dataframe(
                        df_j, text_col, "mak_dt", "mdl_disp_nm", id_col, dtype_val,
                        extra_cols=jn.EXPORT_COLS,
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
