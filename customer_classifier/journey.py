"""
구매 여정 연계 전처리 — Q&A 작성 전/후 고객 행동(장바구니·구매) 분석

PRESET_QNA_JOURNEY_SQL 결과를 받아:
1) 한 문의(q_id)가 여러 구매 건(채널별)과 조인돼 생기는 중복 행을 1건으로 병합
2) 여정 플래그 6종을 우선순위에 따라 단일 journey_stage 로 판정
3) 문의 후 실제 구매로 이어졌는지(구매전환) 산출

여정 플래그는 상호배타적이지 않다(한 문의가 어떤 구매의 '이후'이면서 다른 구매의
'이전'일 수 있음). 아래 우선순위로 하나의 단계만 부여한다:
  구매후 > 검토중(장바구니) > 구매전 > 행동없음
(구매후 문의는 사용·불만 등 사후 이슈일 가능성이 높아 Pain Point 분석에서
 가장 뚜렷한 신호이므로 최우선으로 잡는다.)
"""

import pandas as pd

FLAG_COLS = ["just_ask", "before_d2c", "before_else", "browse_d2c", "after_d2c", "after_else"]

# (플래그, 단계 라벨) — 앞에 있을수록 우선
STAGE_PRIORITY = [
    ("after_d2c",   "구매후(닷컴)"),
    ("after_else",  "구매후(타채널)"),
    ("browse_d2c",  "검토중(장바구니)"),
    ("before_d2c",  "구매전(→닷컴구매)"),
    ("before_else", "구매전(→타채널구매)"),
    ("just_ask",    "행동없음(문의만)"),
]

# 구매 전 단계(전환 분석 대상) 라벨
PRE_PURCHASE_STAGES = {"검토중(장바구니)", "구매전(→닷컴구매)", "구매전(→타채널구매)", "행동없음(문의만)"}

# normalize_dataframe 로 함께 넘길 여정 분석 컬럼 (PII 없음)
EXPORT_COLS = [
    "catg_lvl1_nm", "catg_lvl2_nm",
    "qa_t_gap", "ac_t_gap", "ao_t_gap",
    "a_fail_yn", "ord_chnl",
    "journey_stage", "구매전환",
    "full_a_cntn",
]


def _stage_of(row) -> str:
    for flag, label in STAGE_PRIORITY:
        if row.get(flag, 0) == 1:
            return label
    return "기타"


def _first_valid(s: pd.Series):
    nn = s.dropna()
    return nn.iloc[0] if len(nn) else None


def prepare_journey_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """여정 쿼리 결과 → q_id당 1행으로 병합 + journey_stage·구매전환 부여"""
    df = df_raw.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if "q_id" not in df.columns:
        raise ValueError("여정 쿼리 결과에 q_id 컬럼이 없습니다.")

    for c in FLAG_COLS:
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0).astype(int)
    for c in ["qa_t_gap", "ac_t_gap", "ao_t_gap"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # 행 단위 구매전환: 문의 작성 이후(±2개월 창 내)에 주문이 존재
    mak  = pd.to_datetime(df.get("mak_dttm"), errors="coerce")
    ordr = pd.to_datetime(df.get("ordr_dttm"), errors="coerce")
    df["구매전환"] = (mak.notna() & ordr.notna() & (ordr >= mak)).astype(int)

    # q_id당 1행 병합: 플래그·전환은 max(하나라도 있으면), 리드타임은 min(가장 빠른 행동)
    agg: dict = {c: "max" for c in FLAG_COLS}
    agg["구매전환"] = "max"
    for c in ["ac_t_gap", "ao_t_gap"]:
        if c in df.columns:
            agg[c] = "min"
    if "qa_t_gap" in df.columns:
        agg["qa_t_gap"] = "max"  # 문의당 동일값
    if "a_fail_yn" in df.columns:
        agg["a_fail_yn"] = lambda s: "fail" if (s.astype(str) == "fail").any() else ""
    if "ord_chnl" in df.columns:
        agg["ord_chnl"] = lambda s: ",".join(sorted(set(s.dropna().astype(str)))) or ""
    for c in ["full_q_cntn", "mak_dt", "mak_dttm", "mdl_disp_nm",
              "catg_lvl1_nm", "catg_lvl2_nm", "a_id", "full_a_cntn"]:
        if c in df.columns:
            agg[c] = _first_valid

    g = df.groupby("q_id", as_index=False).agg(agg)
    g["journey_stage"] = g.apply(_stage_of, axis=1)
    return g


def journey_summary(df: pd.DataFrame) -> pd.DataFrame:
    """journey_stage 별 건수·비율 요약 (우선순위 순서 유지)"""
    order = [label for _, label in STAGE_PRIORITY] + ["기타"]
    counts = df["journey_stage"].value_counts()
    rows = [
        {"여정단계": lb, "건수": int(counts[lb]),
         "비율": round(counts[lb] / len(df) * 100, 1)}
        for lb in order if lb in counts.index
    ]
    return pd.DataFrame(rows)
