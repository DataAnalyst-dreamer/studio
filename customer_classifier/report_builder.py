"""
전략 추출용 집계 리포트 생성기

로컬에서 분류를 마친 결과(DataFrame)를 받아, Claude(또는 다른 LLM)의
프로젝트 지식으로 올려 Pain Point·전략을 도출하기 좋은 형태의
**마스킹된 집계 리포트(Markdown)**를 생성합니다.

핵심 설계:
- 원문 수천 건을 통째로 올리지 않고, "집계 + 대표 인용문"만 담아
  외부 반출 데이터 양과 민감도를 최소화한다.
- 모든 대표 인용문은 pii.mask_text로 개인정보를 가린 뒤 담는다.
- 각 인용문에 inquiry_id를 붙여, LLM이 근거를 지목·추적할 수 있게 한다.
- 심각도(severity)를 규칙으로 산출해 우선순위 판단 신호를 함께 제공한다.
"""

from typing import Optional

import pandas as pd

from pii import mask_text
from utils import FAILURE_SUBCATEGORIES, VALUE_SUBCATEGORIES


# ── 심각도(severity) 산출 ────────────────────────────────────────────────
# 실패수요 세부분류별 기본 심각도 (1~5). 금전·반복·구매차단 이슈에 높은 가중.
_SEVERITY_BASE = {
    "결제/환불오류":  5,
    "시스템오류":     4,
    "AS처리지연":     4,
    "오배송/파손":    4,
    "배송지연":       3,
    "상품정보불일치": 3,
    "설치/기사미흡":  3,
    "CS응대불만":     3,
    "기타실패":       2,
}

# 감정·긴급 강도 신호 (있을수록 심각도 가산)
_INTENSITY_WORDS = [
    "최악", "화나", "화가", "실망", "짜증", "황당", "어이", "다신", "다시는",
    "며칠째", "몇 번", "몇번", "반복", "또", "두 번", "세 번", "계속",
    "환불", "취소", "반품", "소비자원", "소비자보호원", "고소", "변호사",
    "당장", "빨리", "급해", "언제까지", "책임",
]


def item_severity(subcat: str, text: str) -> int:
    """세부분류 기본값 + 본문 감정 강도로 1~5 심각도 산출"""
    base = _SEVERITY_BASE.get(subcat, 2)
    t = str(text)
    hits = sum(1 for w in _INTENSITY_WORDS if w in t)
    score = base + (1 if hits >= 1 else 0) + (1 if hits >= 3 else 0)
    return max(1, min(5, score))


# ── 집계 ────────────────────────────────────────────────────────────────

def _safe_month(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce")
    return dt.dt.to_period("M").astype(str).where(dt.notna(), None)


def compute_aggregates(df: pd.DataFrame) -> dict:
    """리포트 작성에 필요한 집계 테이블들을 dict로 반환"""
    total = len(df)

    # 대분류 분포
    cat_counts = df["분류"].value_counts()
    cat_summary = [
        {"분류": c, "건수": int(cat_counts.get(c, 0)),
         "비율": round(cat_counts.get(c, 0) / total * 100, 1) if total else 0.0}
        for c in ["실패수요", "가치수요", "기타", "판단보류", "분류실패"]
        if cat_counts.get(c, 0) > 0
    ]

    fd = df[df["분류"] == "실패수요"].copy()
    vd = df[df["분류"] == "가치수요"].copy()

    # 실패수요 세부분류 순위 + 심각도
    fail_rows = []
    if len(fd):
        fd["_sev"] = [item_severity(s, t) for s, t in zip(fd["세부분류"], fd["text"])]
        for sub, grp in fd.groupby("세부분류"):
            fail_rows.append({
                "세부분류": sub,
                "설명":    FAILURE_SUBCATEGORIES.get(sub, ""),
                "건수":    len(grp),
                "비율":    round(len(grp) / len(fd) * 100, 1),
                "평균심각도": round(grp["_sev"].mean(), 1),
                "고심각건수": int((grp["_sev"] >= 4).sum()),
            })
        fail_rows.sort(key=lambda r: (r["건수"], r["평균심각도"]), reverse=True)

    # 가치수요 세부분류 순위
    val_rows = []
    if len(vd):
        for sub, grp in vd.groupby("세부분류"):
            val_rows.append({
                "세부분류": sub,
                "설명":    VALUE_SUBCATEGORIES.get(sub, ""),
                "건수":    len(grp),
                "비율":    round(len(grp) / len(vd) * 100, 1),
            })
        val_rows.sort(key=lambda r: r["건수"], reverse=True)

    # 상품 × 실패 세부분류 교차 (상품 정보가 있을 때만)
    cross = None
    if len(fd) and "product" in fd.columns and fd["product"].str.strip().ne("").any():
        top_products = fd["product"].replace("", pd.NA).dropna().value_counts().head(10).index
        sub_fd = fd[fd["product"].isin(top_products)]
        if len(sub_fd):
            cross = pd.crosstab(sub_fd["product"], sub_fd["세부분류"])

    # 월별 실패수요 추이 (작성일 있을 때만)
    trend = None
    if len(fd) and "written_at" in fd.columns and fd["written_at"].str.strip().ne("").any():
        fd2 = fd.copy()
        fd2["_월"] = _safe_month(fd2["written_at"])
        fd2 = fd2.dropna(subset=["_월"])
        if len(fd2):
            trend = fd2.groupby(["_월", "세부분류"]).size().unstack(fill_value=0)

    return {
        "total": total,
        "cat_summary": cat_summary,
        "fail_rows": fail_rows,
        "val_rows": val_rows,
        "cross": cross,
        "trend": trend,
        "fd": fd,
        "vd": vd,
    }


def pick_quotes(sub_df: pd.DataFrame, n: int = 8) -> list[dict]:
    """
    세부분류 그룹에서 대표 인용문 n개 선정.
    확신도 높은 순으로 뽑되, 마스킹 후 inquiry_id와 함께 반환.
    """
    cols = sub_df.copy()
    if "확신도" in cols.columns:
        cols = cols.sort_values("확신도", ascending=False)
    quotes = []
    seen = set()
    for _, row in cols.iterrows():
        raw = str(row.get("text", "")).strip()
        key = raw[:40]
        if not raw or key in seen:
            continue
        seen.add(key)
        masked, _ = mask_text(raw)
        masked = masked.replace("\n", " ").strip()
        if len(masked) > 200:
            masked = masked[:200] + "…"
        quotes.append({
            "id":   str(row.get("inquiry_id", "")),
            "text": masked,
            "sev":  item_severity(str(row.get("세부분류", "")), raw),
        })
        if len(quotes) >= n:
            break
    return quotes


# ── Markdown 리포트 ──────────────────────────────────────────────────────

def _fmt_table(headers: list[str], rows: list[list]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
    return "\n".join([line, sep, body])


def build_markdown_report(
    df: pd.DataFrame,
    period_label: str = "",
    quotes_per_sub: int = 8,
) -> str:
    """분류 결과 DataFrame → Claude 프로젝트 지식용 Markdown 리포트"""
    agg = compute_aggregates(df)
    total = agg["total"]
    out: list[str] = []

    out.append("# LGE.COM 고객 문의 분석 리포트 (전략 추출용)")
    out.append("")
    meta_bits = [f"총 분석 건수: **{total:,}건**"]
    if period_label:
        meta_bits.append(f"기간: {period_label}")
    if "data_type" in df.columns:
        types = df["data_type"].value_counts().to_dict()
        meta_bits.append("유형: " + ", ".join(f"{k} {v:,}건" for k, v in types.items()))
    out.append("- " + "\n- ".join(meta_bits))
    out.append("")
    out.append("> 이 리포트는 로컬에서 분류·집계된 결과이며, 대표 인용문은 개인정보가 "
               "마스킹되어 있습니다. 각 인용문의 `[ID]`는 원본 추적용 식별자입니다.")
    out.append("")

    # 1. 수요 구조
    out.append("## 1. 수요 구조 요약")
    out.append("")
    out.append(_fmt_table(
        ["분류", "건수", "비율"],
        [[r["분류"], f'{r["건수"]:,}', f'{r["비율"]}%'] for r in agg["cat_summary"]],
    ))
    out.append("")
    out.append("- **실패수요** = 회사의 실패(오류·지연·누락)로 어쩔 수 없이 생긴 문의 → 개선 과제 원천")
    out.append("- **가치수요** = 구매·사용 의향에서 나온 자연스러운 문의 → 영업·상품 기회")
    out.append("")

    # 2. 실패수요 Pain Point 후보
    out.append("## 2. 실패수요 Pain Point 후보 (세부분류별)")
    out.append("")
    if agg["fail_rows"]:
        out.append("심각도는 세부분류 특성 + 본문 감정강도로 산출한 1~5 지표입니다 (높을수록 시급).")
        out.append("")
        out.append(_fmt_table(
            ["순위", "세부분류", "설명", "건수", "비율", "평균심각도", "고심각(≥4)"],
            [[i + 1, r["세부분류"], r["설명"], f'{r["건수"]:,}', f'{r["비율"]}%',
              r["평균심각도"], r["고심각건수"]]
             for i, r in enumerate(agg["fail_rows"])],
        ))
        out.append("")
        out.append("### 세부분류별 대표 인용문 (개인정보 마스킹)")
        out.append("")
        fd = agg["fd"]
        for r in agg["fail_rows"]:
            sub = r["세부분류"]
            out.append(f"#### {sub} — {r['건수']:,}건 (평균심각도 {r['평균심각도']})")
            quotes = pick_quotes(fd[fd["세부분류"] == sub], n=quotes_per_sub)
            for q in quotes:
                out.append(f"- (심각도 {q['sev']}) \"{q['text']}\" `[{q['id']}]`")
            out.append("")
    else:
        out.append("_실패수요로 분류된 문의가 없습니다._")
        out.append("")

    # 3. 상품 × 실패 교차
    if agg["cross"] is not None:
        out.append("## 3. 상품/카테고리 × 실패수요 교차 분석 (상위 상품)")
        out.append("")
        cross = agg["cross"]
        headers = ["상품/카테고리"] + list(cross.columns)
        rows = [[idx] + [int(v) for v in row] for idx, row in cross.iterrows()]
        out.append(_fmt_table(headers, rows))
        out.append("")
        out.append("> 특정 상품에 실패수요가 집중되면 상품·공급·페이지 단위 원인일 가능성이 큽니다.")
        out.append("")

    # 4. 기간별 추이
    if agg["trend"] is not None:
        out.append("## 4. 실패수요 월별 추이")
        out.append("")
        trend = agg["trend"]
        headers = ["월"] + list(trend.columns)
        rows = [[idx] + [int(v) for v in row] for idx, row in trend.iterrows()]
        out.append(_fmt_table(headers, rows))
        out.append("")
        out.append("> 특정 월에 급증한 세부분류는 이벤트성 원인(프로모션·시스템 배포 등)을 의심하세요.")
        out.append("")

    # 5. 가치수요 기회
    out.append("## 5. 가치수요 기회 요약")
    out.append("")
    if agg["val_rows"]:
        out.append(_fmt_table(
            ["순위", "세부분류", "설명", "건수", "비율"],
            [[i + 1, r["세부분류"], r["설명"], f'{r["건수"]:,}', f'{r["비율"]}%']
             for i, r in enumerate(agg["val_rows"])],
        ))
        out.append("")
        vd = agg["vd"]
        top_val = agg["val_rows"][:3]
        for r in top_val:
            sub = r["세부분류"]
            out.append(f"#### {sub} — {r['건수']:,}건")
            for q in pick_quotes(vd[vd["세부분류"] == sub], n=5):
                out.append(f"- \"{q['text']}\" `[{q['id']}]`")
            out.append("")
    else:
        out.append("_가치수요로 분류된 문의가 없습니다._")
        out.append("")

    # 6. 구매 여정 분석 (여정 연계 쿼리로 추출한 경우에만)
    if "journey_stage" in df.columns:
        out.extend(_journey_section(df))

    # 부록
    out.append("---")
    out.append("## 부록: 분석 지침")
    out.append("")
    out.append(ANALYSIS_GUIDE.strip())
    out.append("")

    return "\n".join(out)


# ── 구매 여정 분석 섹션 ─────────────────────────────────────────────────

_PRE_PURCHASE_STAGES = {"검토중(장바구니)", "구매전(→닷컴구매)", "구매전(→타채널구매)", "행동없음(문의만)"}


def _journey_section(df: pd.DataFrame) -> list[str]:
    """journey_stage·구매전환 컬럼이 있을 때 리포트에 붙는 여정 분석 장"""
    out: list[str] = []
    out.append("## 6. 구매 여정 분석 — 문의 전/후 고객 행동")
    out.append("")
    out.append("문의가 고객 여정의 어느 단계에서 발생했는지와, 문의 후 실제 구매로 "
               "이어졌는지(전환)를 함께 봅니다. **구매를 막는 Pain Point**를 찾는 핵심 신호입니다.")
    out.append("")

    # 6-1. 분류 × 여정 단계 교차
    ct = pd.crosstab(df["journey_stage"], df["분류"])
    headers = ["여정단계"] + list(ct.columns) + ["합계"]
    rows = [[idx] + [int(v) for v in row] + [int(row.sum())] for idx, row in ct.iterrows()]
    out.append("### 6-1. 분류 × 여정 단계")
    out.append("")
    out.append(_fmt_table(headers, rows))
    out.append("")
    out.append("> **구매후 실패수요**는 배송·설치·품질 등 사후 경험 문제, "
               "**구매전/검토중 실패수요**는 구매를 직접 가로막는 문제(전환 손실)입니다. "
               "**행동없음(문의만)** 비중이 큰 세부분류는 문의 단계에서 이탈했을 가능성이 있습니다.")
    out.append("")

    # 6-2. 구매 전 문의의 전환 분석 (세부분류별)
    pre = df[df["journey_stage"].isin(_PRE_PURCHASE_STAGES)].copy()
    if len(pre):
        _empty = pd.Series(index=pre.index, dtype=float)
        pre["구매전환"] = pd.to_numeric(pre.get("구매전환", _empty), errors="coerce").fillna(0)
        pre["_fail"] = (
            pre["a_fail_yn"].astype(str).eq("fail")
            if "a_fail_yn" in pre.columns else pd.Series(False, index=pre.index)
        )
        qa_gap = pd.to_numeric(pre.get("qa_t_gap", _empty), errors="coerce")
        ao_gap = pd.to_numeric(pre.get("ao_t_gap", _empty), errors="coerce")

        rows = []
        for sub, grp in pre.groupby("세부분류"):
            if len(grp) < 1:
                continue
            conv = grp["구매전환"].mean() * 100
            fail_rate = grp["_fail"].mean() * 100
            med_qa = qa_gap.loc[grp.index].median()
            med_ao = ao_gap.loc[grp.index].median()
            rows.append([
                sub, len(grp), f"{conv:.1f}%", f"{fail_rate:.1f}%",
                f"{med_qa:.0f}h" if pd.notna(med_qa) else "-",
                f"{med_ao:.0f}h" if pd.notna(med_ao) else "-",
            ])
        rows.sort(key=lambda r: r[1], reverse=True)

        out.append("### 6-2. 구매 전 문의의 전환 분석 (세부분류별)")
        out.append("")
        out.append(_fmt_table(
            ["세부분류", "건수", "구매전환율", "답변실패율", "응답시간(중앙값)", "답변→주문(중앙값)"],
            rows,
        ))
        out.append("")

        # 6-3. 답변 품질 → 전환 영향
        n_fail = int(pre["_fail"].sum())
        n_ok = len(pre) - n_fail
        if n_fail and n_ok:
            conv_fail = pre.loc[pre["_fail"], "구매전환"].mean() * 100
            conv_ok = pre.loc[~pre["_fail"], "구매전환"].mean() * 100
            out.append("### 6-3. 답변 품질이 전환에 미치는 영향")
            out.append("")
            out.append(_fmt_table(
                ["답변 품질", "건수", "구매전환율"],
                [["정상 답변", n_ok, f"{conv_ok:.1f}%"],
                 ["실패 답변(죄송/안내불가 등)", n_fail, f"{conv_fail:.1f}%"]],
            ))
            out.append("")
            out.append("> 실패 답변의 전환율이 정상 답변보다 낮다면, **답변 커버리지 개선 "
                       "자체가 매출 과제**입니다. 어떤 질문에 답하지 못했는지 6-2와 대표 "
                       "인용문을 대조하세요.")
            out.append("")

    return out


# ── Claude 프로젝트용 지침(시스템 프롬프트) 템플릿 ──────────────────────────

ANALYSIS_GUIDE = """
위 데이터를 근거로 다음을 도출하세요.

1. **Pain Point 도출**: 세부분류를 그대로 쓰지 말고, 대표 인용문을 묶어
   "무엇이·왜 문제인지"가 드러나는 구체적 Pain Point로 재정의하세요.
   각 Pain Point에는 반드시 근거 인용문의 `[ID]`를 2개 이상 붙이세요.
   데이터에 근거가 없는 추정은 하지 마세요.
2. **근본원인**: Pain Point별로 5-Why로 원인을 파고들어 책임 도메인
   (배송/시스템/상품정보/CS/제품/설치)을 지목하세요.
3. **개선과제**: 원인에 대응하는 실행 과제와 기대효과·측정 KPI를 제시하세요.
4. **우선순위**: (빈도 × 평균심각도 × 실현난이도)로 Quick Win / 중기 / 장기로
   구분해 로드맵으로 정리하세요.
5. **여정 데이터가 있으면**(6장): 구매전/검토중 단계의 실패수요는 '전환 손실'로,
   구매후 실패수요는 '사후 경험 문제'로 구분해 과제의 기대효과를 다르게 산정하고,
   답변실패율·전환율 차이를 근거로 활용하세요.
"""

STRATEGY_SYSTEM_PROMPT = """당신은 LGE.COM CS 전략 분석가입니다.
입력으로 받는 것은 고객 문의를 로컬에서 분류·집계한 리포트이며, 대표 인용문에는
개인정보가 마스킹되어 있고 각 인용문에는 추적용 [ID]가 붙어 있습니다.

작업 원칙:
- 실패수요 = 회사의 실패로 생긴 불필요한 문의. 이것이 개선 과제의 원천입니다.
- 가치수요 = 구매·사용 의향의 자연스러운 문의. 영업·상품 기회입니다.
- 모든 주장은 반드시 리포트의 인용문 [ID]로 근거를 대세요. 근거 없는 추정 금지.
- 뻔한 일반론("CS 교육 강화") 대신, 원인에 붙은 구체적 과제를 제시하세요.

진행 순서(한 번에 다 하지 말고 단계별로, 각 단계 뒤 사용자 확인):
① Pain Point 도출 (세부분류를 구체적 문제로 재정의, [ID] 근거 필수)
② 근본원인 분석 (Pain Point별 5-Why, 책임 도메인 지목)
③ 개선과제 생성 (원인 대응 과제 + 기대효과 + KPI)
④ 우선순위·로드맵 (빈도 × 심각도 × 실현난이도 → Quick Win/중기/장기)

먼저 리포트를 읽고 ① Pain Point 도출부터 시작하세요."""


def build_strategy_prompt() -> str:
    """Claude 프로젝트의 '커스텀 인스트럭션'에 붙여넣을 시스템 프롬프트"""
    return STRATEGY_SYSTEM_PROMPT
