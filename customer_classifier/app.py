"""
고객 문의·리뷰 자동 분류 프로그램
LGE.COM CS 전략 과제 — Ollama 로컬 LLM + Amazon Redshift
"""

import random
import time

import pandas as pd
import plotly.express as px
import streamlit as st

import classifier as clf
import data_loader as dl
import db_connector as dbc
import report_builder as rb
from utils import (
    CATEGORY_LABELS,
    FAILURE_SUBCATEGORIES,
    VALUE_SUBCATEGORIES,
    clear_checkpoint,
    load_checkpoint,
    now_str,
    save_checkpoint,
    to_excel_bytes,
)

# ─────────────────────────────────────────────
# 페이지 기본 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="고객 문의·리뷰 자동 분류",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# 테마 색상 팔레트
# ─────────────────────────────────────────────
_DARK = {
    "cat": {
        "실패수요": "#F87171",
        "가치수요": "#4ADE80",
        "기타":    "#9CA3AF",
        "판단보류": "#FCD34D",
        "분류실패": "#64748B",
    },
    "bg":         "#0D1117",
    "sidebar":    "#161B22",
    "panel":      "#1C2128",
    "border":     "#30363D",
    "text":       "#E6EDF3",
    "text_sub":   "#8B949E",
    "text_muted": "#656D76",
    "accent":     "#3FBDAC",
    "ok":   "#4ADE80",
    "warn": "#FCD34D",
    "err":  "#F87171",
    "plot_paper": "#0D1117",
    "plot_bg":    "#1C2128",
    "plot_grid":  "#30363D",
    "plot_font":  "#E6EDF3",
    "infobox_bg":   "#1C2128",
    "infobox_bdr":  "#30363D",
    "infobox_text": "#C9D1D9",
    "infobox_bold": "#E6EDF3",
}

_LIGHT = {
    "cat": {
        "실패수요": "#B91C1C",
        "가치수요": "#15803D",
        "기타":    "#475569",
        "판단보류": "#92400E",
        "분류실패": "#6B7280",
    },
    "bg":         "#F6F8FA",
    "sidebar":    "#FFFFFF",
    "panel":      "#FFFFFF",
    "border":     "#D0D7DE",
    "text":       "#1F2328",
    "text_sub":   "#57606A",
    "text_muted": "#848D97",
    "accent":     "#0D9488",
    "ok":   "#15803D",
    "warn": "#92400E",
    "err":  "#B91C1C",
    "plot_paper": "#FFFFFF",
    "plot_bg":    "#F6F8FA",
    "plot_grid":  "#E5E7EB",
    "plot_font":  "#1F2328",
    "infobox_bg":   "#EFF8FF",
    "infobox_bdr":  "#BAE0FD",
    "infobox_text": "#24292F",
    "infobox_bold": "#0550AE",
}


def _C(key: str) -> str:
    """현재 테마의 색상값 반환"""
    palette = _DARK if st.session_state.get("theme", "다크") == "다크" else _LIGHT
    return palette[key]


def _cat_color(cat: str) -> str:
    palette = _DARK if st.session_state.get("theme", "다크") == "다크" else _LIGHT
    return palette["cat"].get(cat, palette["text"])


def _apply_theme_css() -> None:
    C = _DARK if st.session_state.get("theme", "다크") == "다크" else _LIGHT
    is_dark = C is _DARK

    card_shadow = "" if is_dark else "box-shadow: 0 1px 4px rgba(0,0,0,0.08);"
    sidebar_shadow = "" if is_dark else "box-shadow: 2px 0 8px rgba(0,0,0,0.06);"

    css = f"""
<style>
/* ══════════════════════════════════════
   기본 배경 · 텍스트
══════════════════════════════════════ */
.stApp, [data-testid="stMain"],
.main, .block-container {{
    background-color: {C['bg']} !important;
    color: {C['text']} !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    background-color: {C['sidebar']} !important;
    border-right: 1px solid {C['border']};
    {sidebar_shadow}
}}
/* 헤더(상단 툴바) */
[data-testid="stHeader"] {{
    background-color: {C['bg']} !important;
    border-bottom: 1px solid {C['border']};
}}

/* ══════════════════════════════════════
   텍스트 전반
══════════════════════════════════════ */
.stMarkdown p, .stMarkdown li,
.stMarkdown td, .stMarkdown th,
.stMarkdown h1, .stMarkdown h2,
.stMarkdown h3, .stMarkdown h4,
.element-container p, label, span.st-emotion-cache-1b2d1a4,
[data-testid="stWidgetLabel"] p {{
    color: {C['text']} !important;
}}
h1, h2, h3, h4 {{ color: {C['text']} !important; }}
strong {{ color: {C['text']} !important; }}
code {{ color: {C['accent']} !important; }}

/* ══════════════════════════════════════
   탭
══════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {{
    background: transparent !important;
    border-bottom: 2px solid {C['border']} !important;
    gap: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
}}
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] div {{
    color: {C['text_sub']} !important;
    font-weight: 500;
}}
.stTabs [aria-selected="true"] p,
.stTabs [aria-selected="true"] div {{
    color: {C['accent']} !important;
    font-weight: 700;
}}
.stTabs [aria-selected="true"] {{
    border-bottom: 2px solid {C['accent']} !important;
}}

/* ══════════════════════════════════════
   입력 위젯
══════════════════════════════════════ */
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div,
[data-testid="stNumberInput"] > div > div,
[data-testid="stTextArea"] textarea {{
    background-color: {C['panel']} !important;
    color: {C['text']} !important;
    border-color: {C['border']} !important;
}}
[data-testid="stSlider"] > div {{ color: {C['text']} !important; }}

/* ══════════════════════════════════════
   라디오 버튼
══════════════════════════════════════ */
[data-testid="stRadio"] label span {{ color: {C['text']} !important; }}

/* ══════════════════════════════════════
   Expander
══════════════════════════════════════ */
[data-testid="stExpander"] details summary {{
    background-color: {C['panel']} !important;
    border: 1px solid {C['border']} !important;
    border-radius: 8px;
}}
[data-testid="stExpander"] details summary span,
[data-testid="stExpander"] details summary p {{
    color: {C['text']} !important;
    font-weight: 600;
}}
[data-testid="stExpander"] details {{
    border: 1px solid {C['border']} !important;
    border-radius: 8px;
}}

/* ══════════════════════════════════════
   데이터프레임
══════════════════════════════════════ */
[data-testid="stDataFrame"] {{
    border: 1px solid {C['border']} !important;
    border-radius: 8px;
}}

/* ══════════════════════════════════════
   커스텀 컴포넌트
══════════════════════════════════════ */
.metric-card {{
    background: {C['panel']} !important;
    border: 1px solid {C['border']} !important;
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
    {card_shadow}
}}
.metric-card .m-label {{
    font-size: 13px;
    color: {C['text_sub']};
    margin-bottom: 8px;
    font-weight: 500;
}}
.metric-card .m-value {{
    font-size: 30px;
    font-weight: 800;
    line-height: 1.1;
}}
.metric-card .m-pct {{
    font-size: 13px;
    color: {C['text_muted']};
    margin-top: 6px;
}}

.section-title {{
    font-size: 17px;
    font-weight: 700;
    color: {C['text']};
    border-left: 3px solid {C['accent']};
    padding-left: 12px;
    margin: 28px 0 14px;
}}

.info-box {{
    background: {C['infobox_bg']};
    border: 1px solid {C['infobox_bdr']};
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 14px;
    color: {C['infobox_text']};
    line-height: 1.65;
}}
.info-box b {{ color: {C['infobox_bold']}; }}

.status-ok   {{ color: {C['ok']};   font-weight: 700; }}
.status-warn {{ color: {C['warn']}; font-weight: 700; }}
.status-err  {{ color: {C['err']};  font-weight: 700; }}

/* ══════════════════════════════════════
   알림박스 (st.info / st.warning / st.error)
══════════════════════════════════════ */
[data-testid="stAlert"] p {{ color: {C['text']} !important; }}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def _plotly_layout() -> dict:
    C = _DARK if st.session_state.get("theme", "다크") == "다크" else _LIGHT
    return {
        "paper_bgcolor": C["plot_paper"],
        "plot_bgcolor":  C["plot_bg"],
        "font_color":    C["plot_font"],
        "gridcolor":     C["plot_grid"],
    }


# ─────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────
def _init_state():
    defaults = {
        "theme":            "다크",
        "standard_df":      None,
        "result_df":        None,
        "sample_result":    None,
        "is_running":       False,
        "stop_flag":        [False],
        "db_conn":          None,
        "db_driver":        None,
        "selected_model":   None,
        "confidence_threshold": 75,
        "_db_preview":      None,   # DB 조회 결과 임시 보관 (버튼 타이밍 문제 해결)
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ─────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 고객 문의·리뷰 분류")

    # ── 테마 선택 ──
    theme_choice = st.radio(
        "🎨 화면 테마",
        ["다크", "라이트"],
        horizontal=True,
        index=0 if st.session_state["theme"] == "다크" else 1,
        key="_theme_radio",
    )
    if theme_choice != st.session_state["theme"]:
        st.session_state["theme"] = theme_choice
        st.rerun()

    st.markdown("---")

    # ── Ollama 상태 ──
    st.markdown("### ⚙️ LLM 엔진 상태")
    ollama_ok, ollama_msg = clf.check_ollama()
    if ollama_ok:
        st.markdown('<span class="status-ok">● Ollama 실행 중</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-err">● Ollama 미실행</span>', unsafe_allow_html=True)
        st.error(ollama_msg)
        st.markdown(
            "**Ollama 시작 방법:**\n\n"
            "터미널(명령 프롬프트)에서:\n"
            "```\nollama serve\n```"
        )

    # ── 모델 선택 ──
    models = clf.list_models()
    if models:
        preferred = [m for m in models if any(k in m for k in ["exaone", "qwen", "gemma"])]
        ordered = preferred + [m for m in models if m not in preferred]
        selected_model = st.selectbox("🤖 분류 모델 선택", ordered)
        st.session_state["selected_model"] = selected_model
        st.markdown(
            '<div class="info-box">'
            "<b>모델 추천 순서 (RAM 기준):</b><br>"
            "① <b>qwen2.5:3b</b> — RAM 4GB 이상 (권장)<br>"
            "② <b>gemma2:2b</b> — RAM 3GB 이상 (초경량)<br>"
            "③ <b>exaone3.5</b> — RAM 10GB 이상 (한국어 최우수)<br>"
            "④ <b>qwen2.5:7b</b> — RAM 8GB 이상<br><br>"
            "<b>RAM 부족 오류 시:</b> <code>ollama pull qwen2.5:3b</code>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("설치된 모델이 없습니다.")
        st.markdown(
            "아래 명령어로 모델을 설치하세요:\n"
            "```\nollama pull exaone3.5\n```"
        )
        st.session_state["selected_model"] = None

    st.markdown("---")

    # ── 중간 저장 불러오기 ──
    checkpoint = load_checkpoint()
    if checkpoint:
        st.markdown("### 💾 이전 작업 발견")
        saved_at    = checkpoint.get("saved_at", "알 수 없음")
        saved_count = checkpoint.get("processed_count", 0)
        st.info(f"저장 시각: {saved_at}\n처리 완료: {saved_count:,}건")
        col_resume, col_discard = st.columns(2)
        with col_resume:
            if st.button("▶ 이어하기", use_container_width=True):
                st.session_state["standard_df"] = checkpoint.get("standard_df")
                st.session_state["result_df"]   = checkpoint.get("result_df")
                st.rerun()
        with col_discard:
            if st.button("🗑 버리기", use_container_width=True):
                clear_checkpoint()
                st.rerun()

# ─────────────────────────────────────────────
# CSS 주입 (테마 선택 후)
# ─────────────────────────────────────────────
_apply_theme_css()

# ─────────────────────────────────────────────
# 메인 영역
# ─────────────────────────────────────────────
st.markdown("# 🔍 고객 문의·리뷰 자동 분류 프로그램")
st.markdown(
    "고객 Q&A 및 상품 리뷰를 **실패수요 / 가치수요 / 기타 / 판단보류**로 자동 분류합니다. "
    "사내 Ollama 로컬 LLM을 사용하므로 외부 인터넷 없이 동작합니다."
)

tab_input, tab_classify, tab_result, tab_report, tab_help = st.tabs(
    ["📂 1단계: 데이터 입력", "▶ 2단계: 분류 실행", "📊 3단계: 결과·검토",
     "🧭 4단계: 전략 리포트", "❓ 도움말"]
)


# ══════════════════════════════════════════════
# 탭 1 — 데이터 입력
# ══════════════════════════════════════════════
with tab_input:
    st.markdown('<div class="section-title">데이터 입력 방식 선택</div>', unsafe_allow_html=True)

    input_method = st.radio(
        "입력 방식",
        ["📁 파일 업로드 (Excel/CSV)", "🗄️ DB 직접 연결 (Amazon Redshift)"],
        horizontal=True,
    )
    data_type = st.selectbox("데이터 유형", ["Q&A", "리뷰", "Q&A+리뷰 혼합"])

    st.markdown("---")

    # ── 파일 업로드 ──
    if input_method.startswith("📁"):
        uploaded = st.file_uploader(
            "Excel(.xlsx) 또는 CSV 파일을 올려주세요",
            type=["xlsx", "xls", "csv"],
        )
        if uploaded:
            df = dl.load_from_file(uploaded, data_type)
            if df is not None and len(df) > 0:
                st.success(f"✅ {len(df):,}건 로드 완료")
                st.markdown("**표준 형식 미리보기 (상위 10행)**")
                st.dataframe(df.head(10), use_container_width=True)
                if st.button("💾 이 데이터로 분류 준비 완료", type="primary"):
                    st.session_state["standard_df"] = df
                    st.session_state["result_df"]   = None
                    clear_checkpoint()
                    st.success("2단계 탭에서 분류를 시작할 수 있습니다.")

    # ── DB 연결 ──
    else:
        st.markdown('<div class="section-title">DB 접속 정보 (.env 파일)</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="info-box">'
            "접속 정보는 프로그램 폴더의 <b>.env</b> 파일에서 불러옵니다. "
            ".env.example 파일을 복사해 .env 로 이름을 바꾼 뒤 값을 입력하세요.<br><br>"
            "테이블명·컬럼명을 모르면 사내 IT/DBA에 "
            "<b>'Q&A·리뷰 데이터가 담긴 테이블명·컬럼명'</b>을 문의하세요. "
            "분석용으로는 <b>읽기 전용 계정</b>을 별도 발급받는 것을 권장합니다."
            "</div>",
            unsafe_allow_html=True,
        )

        env_ok, env_msg = dbc.check_env()
        if not env_ok:
            st.error(env_msg)
        else:
            if st.button("🔌 DB 연결 테스트"):
                with st.spinner("연결 중..."):
                    ok, msg = dbc.test_connection()
                if ok:
                    conn, driver = dbc.get_connection()
                    st.session_state["db_conn"]   = conn
                    st.session_state["db_driver"] = driver
                    st.success(msg)
                else:
                    st.error(msg)

            if st.session_state["db_conn"]:
                # load_from_db는 "쿼리 실행" 버튼을 클릭한 렌더링에서만 DataFrame을 반환함.
                # "분류 준비 완료" 버튼 클릭 시 스크립트가 재실행되면 None이 반환되므로,
                # 결과를 session_state에 캐시해 두고 캐시에서 읽는다.
                newly_loaded = dl.load_from_db(st.session_state["db_conn"], data_type)
                if newly_loaded is not None and len(newly_loaded) > 0:
                    st.session_state["_db_preview"] = newly_loaded

                preview_df = st.session_state.get("_db_preview")
                if preview_df is not None:
                    st.success(f"✅ {len(preview_df):,}건 로드 완료 — 아래 버튼을 클릭해 분류 단계로 진행하세요.")
                    if st.button("💾 이 데이터로 분류 준비 완료", type="primary", key="db_ready"):
                        st.session_state["standard_df"] = preview_df
                        st.session_state["_db_preview"] = None
                        st.session_state["result_df"]   = None
                        clear_checkpoint()
                        st.rerun()


# ══════════════════════════════════════════════
# 탭 2 — 분류 실행
# ══════════════════════════════════════════════
with tab_classify:
    std_df = st.session_state.get("standard_df")

    if std_df is None:
        st.info("1단계 탭에서 데이터를 먼저 불러와 주세요.")
        st.stop()

    model = st.session_state.get("selected_model")
    if not model:
        st.warning("사이드바에서 Ollama 모델을 선택해주세요.")
        st.stop()

    st.markdown(f"**준비된 데이터:** {len(std_df):,}건 &nbsp;|&nbsp; **사용 모델:** `{model}`")

    result_df = st.session_state.get("result_df")
    if result_df is not None:
        completed = result_df["분류"].notna().sum()
        st.success(f"이미 분류가 완료됐습니다. ({completed:,}/{len(std_df):,}건) — 3단계 탭에서 결과를 확인하세요.")
        if st.button("🔄 처음부터 다시 분류"):
            st.session_state["result_df"] = None
            clear_checkpoint()
            st.rerun()

    else:
        st.markdown('<div class="section-title">분류 실행 옵션</div>', unsafe_allow_html=True)

        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            confidence_threshold = st.slider(
                "낮은 확신도 기준 (이하는 검토 필요 표시)",
                min_value=50, max_value=90, value=75, step=5,
            )
        with col_opt2:
            checkpoint_interval = st.number_input(
                "중간 저장 간격 (N건마다 자동 저장)",
                min_value=10, max_value=500, value=50, step=10,
            )

        use_rules = st.checkbox(
            "⚡ 규칙 사전분류 사용 (명백한 문의는 LLM 없이 즉시 분류 — 속도 향상)",
            value=True,
            help="배송지연·환불오류·시스템오류·파손·호환성 등 아주 명확한 표현은 "
                 "규칙으로 바로 분류해 LLM 호출량을 줄입니다. 사양이 낮은 PC에서 특히 유용합니다. "
                 "결과의 '출처' 열에서 규칙/LLM을 구분할 수 있습니다.",
        )
        st.session_state["use_rules"] = use_rules

        st.markdown("---")

        # ── 진단 도구 ──
        with st.expander("🔧 분류 진단 — 결과가 모두 0이거나 이상할 때 먼저 실행하세요"):
            st.markdown(
                "1건만 분류해 Ollama 응답을 그대로 보여줍니다. "
                "결과가 모두 0이면 여기서 원인을 확인하세요."
            )
            if st.button("🔧 진단 테스트 (1건)", key="diag_btn"):
                test_text = std_df["text"].iloc[0]
                st.markdown(f"**테스트 본문:** `{test_text[:300]}`")
                with st.spinner("Ollama에 요청 중..."):
                    diag = clf.diagnose_one(test_text, model)

                c_http, c_err = st.columns(2)
                with c_http:
                    st.metric("HTTP 상태 코드", diag.get("http_status", "N/A"))
                with c_err:
                    err = diag.get("ollama_error", "")
                    if err:
                        st.error(f"Ollama 오류: {err}")
                    else:
                        st.success("Ollama 오류 없음")

                st.markdown("**Ollama 원본 응답 (raw)**")
                raw = diag.get("raw_response", "")
                st.code(raw if raw else "(응답 없음)", language="json")

                st.markdown("**파싱된 JSON**")
                parsed = diag.get("parsed_json")
                if parsed:
                    st.json(parsed)
                else:
                    st.warning("JSON 파싱 실패 — 위 원본 응답을 확인하세요.")

                st.markdown("**최종 분류 결과**")
                final = diag.get("final_result")
                if final:
                    st.json(final)

                # RAM 오류 감지 (unable to allocate CPU buffer 등)
                err_lower = err.lower() if err else ""
                is_ram_error = any(kw in err_lower for kw in [
                    "allocate", "cpu buffer", "out of memory", "oom",
                    "memory", "terminated", "panic",
                ])

                if is_ram_error:
                    st.error(
                        "🔴 **RAM 부족 오류** — 현재 모델을 실행할 메모리가 부족합니다.\n\n"
                        "**해결 방법 (PowerShell/터미널):**\n"
                        "```powershell\n"
                        "ollama pull qwen2.5:3b\n"
                        "ollama run qwen2.5:3b \"테스트\"\n"
                        "```\n"
                        "설치 후 사이드바 모델 목록에서 `qwen2.5:3b` 또는 `gemma2:2b`로 변경하세요.\n\n"
                        "| 모델 | 필요 RAM | 한국어 |  \n"
                        "|------|----------|--------|  \n"
                        "| qwen2.5:3b | 4GB | 양호 |  \n"
                        "| gemma2:2b | 3GB | 보통 |  \n"
                        "| qwen2.5:7b | 8GB | 우수 |  \n"
                        "| exaone3.5 | 10GB | 최우수 |  \n"
                    )
                else:
                    st.markdown(
                        "---\n"
                        "**원본 응답이 비어있거나 오류가 있다면:**\n"
                        "- `ollama serve` 재실행 후 다시 시도\n"
                        "- 사이드바에서 다른 모델 선택\n\n"
                        "**원본 응답은 있지만 파싱 실패라면:**\n"
                        "- 모델이 JSON 형식을 지키지 않는 것 → 다른 모델 시도\n"
                        "- 권장 소형 모델: `ollama pull qwen2.5:3b`"
                    )

        # ── 샘플 검증 ──
        st.markdown("### 🔬 샘플 검증 (권장)")
        st.markdown(
            "전체 분류 전에 소량 샘플로 품질을 먼저 확인하는 것을 **강력히 권장**합니다. "
            "샘플 결과를 보고 분류 기준을 조정한 뒤 전체를 실행하세요."
        )
        sample_size = st.number_input(
            "샘플 건수",
            min_value=10, max_value=min(500, len(std_df)),
            value=min(100, len(std_df)), step=10,
        )
        if st.button("🔬 샘플 검증 시작", disabled=not model):
            sample_indices = random.sample(range(len(std_df)), int(sample_size))
            sample_df = std_df.iloc[sample_indices].copy().reset_index(drop=True)

            progress_bar = st.progress(0, text="샘플 분류 중...")
            status_text  = st.empty()
            results = []
            for i, row in sample_df.iterrows():
                result = clf.classify_one(
                    row["text"], model,
                    use_rules=st.session_state.get("use_rules", True),
                )
                results.append(result)
                pct = (i + 1) / len(sample_df)
                progress_bar.progress(pct, text=f"샘플 분류 중... {i+1}/{len(sample_df)}")
                status_text.text(f"최근 분류: [{result['분류']}] {row['text'][:50]}...")

            sample_result = pd.concat(
                [sample_df.reset_index(drop=True), pd.DataFrame(results)], axis=1
            )
            st.session_state["sample_result"] = sample_result
            progress_bar.empty()
            status_text.empty()
            st.success("샘플 분류 완료!")

        sample_result = st.session_state.get("sample_result")
        if sample_result is not None:
            st.markdown("**샘플 분류 결과**")
            counts = sample_result["분류"].value_counts()
            total_sample = len(sample_result)
            fail_n = counts.get("분류실패", 0)

            # 분류실패가 절반 이상이면 경고
            if fail_n > total_sample * 0.5:
                st.warning(
                    f"⚠️ 분류실패가 {fail_n}건 ({fail_n/total_sample*100:.0f}%)입니다. "
                    "위 **🔧 진단 도구**를 실행해 원인을 확인하세요."
                )

            # 5개 카드 (분류실패 포함)
            c1, c2, c3, c4, c5 = st.columns(5)
            for col_w, cat in zip(
                [c1, c2, c3, c4, c5],
                ["실패수요", "가치수요", "기타", "판단보류", "분류실패"],
            ):
                with col_w:
                    n   = counts.get(cat, 0)
                    pct = n / total_sample * 100
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="m-label">{CATEGORY_LABELS[cat]}</div>'
                        f'<div class="m-value" style="color:{_cat_color(cat)}">{n}</div>'
                        f'<div class="m-pct">{pct:.1f}%</div></div>',
                        unsafe_allow_html=True,
                    )

            st.markdown(f"전체 샘플: **{total_sample}건**")
            sample_cols = [c for c in ["text", "분류", "세부분류", "세부사유", "확신도"] if c in sample_result.columns]
            st.dataframe(
                sample_result[sample_cols].head(20),
                use_container_width=True,
            )

        st.markdown("---")

        # ── 전체 분류 ──
        st.markdown("### ▶ 전체 분류 실행")
        btn_col1, btn_col2 = st.columns([2, 1])
        with btn_col1:
            run_btn = st.button(
                f"▶ 전체 분류 시작 ({len(std_df):,}건)",
                type="primary",
                disabled=not model or st.session_state["is_running"],
            )
        with btn_col2:
            stop_btn = st.button("⏹ 중단", disabled=not st.session_state["is_running"])

        if stop_btn:
            st.session_state["stop_flag"][0] = True
            st.warning("중단 요청됨. 현재 처리 중인 건이 완료되면 멈춥니다.")

        if run_btn and not st.session_state["is_running"]:
            st.session_state["is_running"] = True
            st.session_state["stop_flag"]  = [False]

            progress_bar = st.progress(0, text="분류 준비 중...")
            status_text  = st.empty()
            elapsed_text = st.empty()
            start_time   = time.time()

            def on_progress(current, total):
                pct      = current / total
                elapsed  = time.time() - start_time
                rate     = current / elapsed if elapsed > 0 else 0
                remaining = (total - current) / rate if rate > 0 else 0
                progress_bar.progress(pct, text=f"분류 중... {current:,}/{total:,}건 ({pct*100:.1f}%)")
                elapsed_text.text(
                    f"경과: {elapsed:.0f}초 | 남은 예상 시간: {remaining:.0f}초 | 속도: {rate:.1f}건/초"
                )

            def on_checkpoint(partial_results):
                partial_df  = pd.DataFrame(partial_results)
                partial_std = std_df.iloc[: len(partial_results)].copy().reset_index(drop=True)
                merged      = pd.concat([partial_std, partial_df], axis=1)
                save_checkpoint({
                    "standard_df":     std_df,
                    "result_df":       merged,
                    "processed_count": len(partial_results),
                    "saved_at":        now_str(),
                })

            texts = std_df["text"].tolist()
            raw_results = clf.classify_batch(
                texts, model,
                progress_callback=on_progress,
                stop_flag=st.session_state["stop_flag"],
                checkpoint_callback=on_checkpoint,
                checkpoint_interval=int(checkpoint_interval),
                use_rules=use_rules,
            )

            result_records = pd.DataFrame(raw_results)
            processed_std  = std_df.iloc[: len(raw_results)].copy().reset_index(drop=True)
            final_df       = pd.concat([processed_std, result_records], axis=1)
            final_df["검토완료"] = False

            st.session_state["result_df"]             = final_df
            st.session_state["is_running"]            = False
            st.session_state["confidence_threshold"]  = confidence_threshold
            clear_checkpoint()

            progress_bar.empty()
            status_text.empty()
            elapsed_text.empty()

            total_time = time.time() - start_time
            if st.session_state["stop_flag"][0]:
                st.warning(f"중단됨. {len(raw_results):,}/{len(std_df):,}건 처리 완료. (소요 {total_time:.0f}초)")
            else:
                st.success(f"✅ 분류 완료! {len(raw_results):,}건 처리. (소요 {total_time:.0f}초)")
            st.rerun()


# ══════════════════════════════════════════════
# 탭 3 — 결과 및 검토
# ══════════════════════════════════════════════
with tab_result:
    result_df = st.session_state.get("result_df")

    if result_df is None:
        st.info("2단계 탭에서 분류를 먼저 실행해주세요.")
        st.stop()

    confidence_threshold = st.session_state.get("confidence_threshold", 75)
    PL = _plotly_layout()

    # ── 요약 지표 ──
    st.markdown('<div class="section-title">📊 분류 결과 요약</div>', unsafe_allow_html=True)
    total  = len(result_df)
    counts = result_df["분류"].value_counts()

    metric_cols = st.columns(5)
    for i, (cat, label) in enumerate(CATEGORY_LABELS.items()):
        n   = counts.get(cat, 0)
        pct = n / total * 100 if total > 0 else 0
        with metric_cols[i]:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="m-label">{label}</div>'
                f'<div class="m-value" style="color:{_cat_color(cat)}">{n:,}</div>'
                f'<div class="m-pct">{pct:.1f}%</div></div>',
                unsafe_allow_html=True,
            )
    st.markdown(f"<br>**전체:** {total:,}건", unsafe_allow_html=True)

    # ── 차트 ──
    st.markdown('<div class="section-title">📈 차트</div>', unsafe_allow_html=True)
    chart_col1, chart_col2 = st.columns(2)

    cat_colors = (_DARK if st.session_state["theme"] == "다크" else _LIGHT)["cat"]

    with chart_col1:
        pie_data = pd.DataFrame({
            "분류": list(CATEGORY_LABELS.keys()),
            "건수": [counts.get(c, 0) for c in CATEGORY_LABELS],
        })
        pie_data = pie_data[pie_data["건수"] > 0]
        fig_pie = px.pie(
            pie_data, names="분류", values="건수",
            color="분류", color_discrete_map=cat_colors,
            title="분류 비율",
        )
        fig_pie.update_layout(
            paper_bgcolor=PL["paper_bgcolor"],
            plot_bgcolor=PL["plot_bgcolor"],
            font_color=PL["font_color"],
            title_font_size=15,
        )
        fig_pie.update_traces(textfont_color=PL["font_color"])
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        fd = result_df[result_df["분류"] == "실패수요"]
        if len(fd) > 0 and "세부사유" in fd.columns:
            top_reasons = fd["세부사유"].value_counts().head(10).reset_index()
            top_reasons.columns = ["세부사유", "건수"]
            fig_bar = px.bar(
                top_reasons, x="건수", y="세부사유", orientation="h",
                title="실패수요 세부사유 Top 10",
                color_discrete_sequence=[cat_colors["실패수요"]],
            )
            fig_bar.update_layout(
                paper_bgcolor=PL["paper_bgcolor"],
                plot_bgcolor=PL["plot_bgcolor"],
                font_color=PL["font_color"],
                yaxis={"autorange": "reversed", "gridcolor": PL["gridcolor"]},
                xaxis={"gridcolor": PL["gridcolor"]},
                title_font_size=15,
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("실패수요 데이터가 없어 세부사유 차트를 표시할 수 없습니다.")

    # 기간별 추이
    if "written_at" in result_df.columns and result_df["written_at"].str.strip().ne("").any():
        try:
            df_dated = result_df.copy()
            df_dated["날짜"] = pd.to_datetime(df_dated["written_at"], errors="coerce")
            df_dated = df_dated.dropna(subset=["날짜"])
            if len(df_dated) > 0:
                df_dated["월"] = df_dated["날짜"].dt.to_period("M").astype(str)
                trend = df_dated.groupby(["월", "분류"]).size().reset_index(name="건수")
                fig_trend = px.line(
                    trend, x="월", y="건수", color="분류",
                    color_discrete_map=cat_colors,
                    title="월별 분류 추이", markers=True,
                )
                fig_trend.update_layout(
                    paper_bgcolor=PL["paper_bgcolor"],
                    plot_bgcolor=PL["plot_bgcolor"],
                    font_color=PL["font_color"],
                    yaxis={"gridcolor": PL["gridcolor"]},
                    xaxis={"gridcolor": PL["gridcolor"]},
                    title_font_size=15,
                )
                st.plotly_chart(fig_trend, use_container_width=True)
        except Exception:
            pass

    # ── 세부분류 분석 (과제 도출용) ──
    if "세부분류" in result_df.columns:
        st.markdown('<div class="section-title">🎯 세부분류 분석 — 개선 과제 도출</div>', unsafe_allow_html=True)

        sub_col1, sub_col2 = st.columns(2)

        with sub_col1:
            fd = result_df[result_df["분류"] == "실패수요"].copy()
            if len(fd) > 0:
                # 실패수요 세부분류 순위표
                sub_counts = fd["세부분류"].value_counts().reset_index()
                sub_counts.columns = ["세부분류", "건수"]
                sub_counts["설명"] = sub_counts["세부분류"].map(FAILURE_SUBCATEGORIES).fillna("")
                sub_counts["비율"] = (sub_counts["건수"] / len(fd) * 100).round(1).astype(str) + "%"
                sub_counts["과제 우선순위"] = range(1, len(sub_counts) + 1)

                err_color = _C("err")
                fig_fail = px.bar(
                    sub_counts, x="건수", y="세부분류", orientation="h",
                    title=f"실패수요 세부분류 ({len(fd):,}건)",
                    color_discrete_sequence=[err_color],
                    text="건수",
                )
                fig_fail.update_layout(
                    paper_bgcolor=PL["paper_bgcolor"],
                    plot_bgcolor=PL["plot_bgcolor"],
                    font_color=PL["font_color"],
                    yaxis={"autorange": "reversed", "gridcolor": PL["gridcolor"]},
                    xaxis={"gridcolor": PL["gridcolor"]},
                    title_font_size=14,
                    margin={"l": 10, "r": 10},
                )
                st.plotly_chart(fig_fail, use_container_width=True)

                st.markdown("**실패수요 개선 과제 우선순위**")
                st.dataframe(
                    sub_counts[["과제 우선순위", "세부분류", "설명", "건수", "비율"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("실패수요 데이터가 없습니다.")

        with sub_col2:
            vd = result_df[result_df["분류"] == "가치수요"].copy()
            if len(vd) > 0:
                sub_counts_v = vd["세부분류"].value_counts().reset_index()
                sub_counts_v.columns = ["세부분류", "건수"]
                sub_counts_v["설명"] = sub_counts_v["세부분류"].map(VALUE_SUBCATEGORIES).fillna("")
                sub_counts_v["비율"] = (sub_counts_v["건수"] / len(vd) * 100).round(1).astype(str) + "%"
                sub_counts_v["기회 우선순위"] = range(1, len(sub_counts_v) + 1)

                ok_color = _C("ok")
                fig_val = px.bar(
                    sub_counts_v, x="건수", y="세부분류", orientation="h",
                    title=f"가치수요 세부분류 ({len(vd):,}건)",
                    color_discrete_sequence=[ok_color],
                    text="건수",
                )
                fig_val.update_layout(
                    paper_bgcolor=PL["paper_bgcolor"],
                    plot_bgcolor=PL["plot_bgcolor"],
                    font_color=PL["font_color"],
                    yaxis={"autorange": "reversed", "gridcolor": PL["gridcolor"]},
                    xaxis={"gridcolor": PL["gridcolor"]},
                    title_font_size=14,
                    margin={"l": 10, "r": 10},
                )
                st.plotly_chart(fig_val, use_container_width=True)

                st.markdown("**가치수요 대응 기회 우선순위**")
                st.dataframe(
                    sub_counts_v[["기회 우선순위", "세부분류", "설명", "건수", "비율"]],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("가치수요 데이터가 없습니다.")

    # ── 검토·수정 표 ──
    st.markdown('<div class="section-title">🔎 검토 및 수정</div>', unsafe_allow_html=True)

    # 실패수요 세부분류 필터 옵션
    fail_sub_opts = [f"실패:{s}" for s in FAILURE_SUBCATEGORIES]
    val_sub_opts  = [f"가치:{s}" for s in VALUE_SUBCATEGORIES]
    review_filter = st.selectbox(
        "표시 필터",
        ["전체", f"확신도 낮음 ({confidence_threshold} 미만)",
         "── 대분류 ──",
         "실패수요", "가치수요", "기타", "판단보류", "분류실패",
         "── 실패수요 세부분류 ──",
         *fail_sub_opts,
         "── 가치수요 세부분류 ──",
         *val_sub_opts,
        ],
    )

    filtered = result_df.copy()
    if review_filter == f"확신도 낮음 ({confidence_threshold} 미만)":
        filtered = filtered[filtered["확신도"].astype(float) < confidence_threshold]
    elif review_filter in ["실패수요", "가치수요", "기타", "판단보류", "분류실패"]:
        filtered = filtered[filtered["분류"] == review_filter]
    elif review_filter.startswith("실패:") or review_filter.startswith("가치:"):
        _, sub = review_filter.split(":", 1)
        filtered = filtered[filtered.get("세부분류", pd.Series(dtype=str)) == sub] if "세부분류" in filtered.columns else filtered
    elif review_filter.startswith("──"):
        pass  # 구분선 선택 시 전체 표시

    st.markdown(f"표시 중: **{len(filtered):,}건**")

    category_options = ["실패수요", "가치수요", "기타", "판단보류", "분류실패"]
    all_subcat_opts  = (
        list(FAILURE_SUBCATEGORIES.keys()) +
        list(VALUE_SUBCATEGORIES.keys()) +
        ["해당없음"]
    )
    display_cols   = ["inquiry_id", "data_type", "text", "분류", "세부분류", "세부사유", "확신도", "출처", "journey_stage", "구매전환"]
    available_cols = [c for c in display_cols if c in filtered.columns]

    if len(filtered) > 0:
        edited_df = st.data_editor(
            filtered[available_cols],
            column_config={
                "분류":       st.column_config.SelectboxColumn("분류", options=category_options, required=True),
                "세부분류":   st.column_config.SelectboxColumn("세부분류", options=all_subcat_opts),
                "text":       st.column_config.TextColumn("본문", width="large"),
                "확신도":     st.column_config.NumberColumn("확신도", min_value=0, max_value=100, format="%d"),
                "inquiry_id": st.column_config.TextColumn("ID", width="small"),
                "data_type":  st.column_config.TextColumn("유형", width="small"),
                "세부사유":   st.column_config.TextColumn("세부사유", width="medium"),
                "출처":       st.column_config.TextColumn("출처", width="small", disabled=True),
            },
            use_container_width=True,
            num_rows="fixed",
            key="review_editor",
        )

        if st.button("💾 수정 내용 반영"):
            for idx, row in edited_df.iterrows():
                if idx in filtered.index:
                    st.session_state["result_df"].at[idx, "분류"] = row["분류"]
                    if "세부분류" in row:
                        st.session_state["result_df"].at[idx, "세부분류"] = row["세부분류"]
            st.success("수정 내용이 결과에 반영됐습니다.")
            st.rerun()
    else:
        st.info("해당 필터에 맞는 항목이 없습니다.")

    # ── 다운로드 ──
    st.markdown('<div class="section-title">📥 결과 다운로드</div>', unsafe_allow_html=True)
    final      = st.session_state["result_df"]
    excel_bytes = to_excel_bytes(final)
    filename   = f"분류결과_{now_str()}.xlsx"
    st.download_button(
        label="📥 Excel 파일 다운로드 (원본 + 분류 결과)",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    st.markdown(
        f"다운로드 파일에는 원본 데이터에 **분류, 세부사유, 근거, 확신도** 4개 컬럼이 추가됩니다. "
        f"파일명: `{filename}`"
    )


# ══════════════════════════════════════════════
# 탭 4 — 전략 리포트 (Claude 프로젝트 연계)
# ══════════════════════════════════════════════
with tab_report:
    result_df = st.session_state.get("result_df")

    if result_df is None:
        st.info("2단계에서 분류를 먼저 실행한 뒤, 3단계에서 결과를 검토하고 이 탭으로 오세요.")
        st.stop()

    st.markdown('<div class="section-title">🧭 전략 추출용 리포트 생성</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">'
        "로컬 분류 결과를 <b>개인정보가 마스킹된 집계 리포트</b>로 만들어, "
        "<b>Claude 프로젝트</b>(또는 사내 승인 LLM)에 올려 Pain Point·개선과제·전략을 "
        "도출할 수 있습니다.<br><br>"
        "원문 수천 건을 통째로 올리지 않고 <b>집계 + 대표 인용문</b>만 담으므로, "
        "외부로 나가는 데이터 양과 민감도가 최소화됩니다. "
        "각 인용문에는 추적용 <code>[ID]</code>가 붙어 근거를 되짚을 수 있습니다."
        "</div>",
        unsafe_allow_html=True,
    )

    # 분류 대상만 (실패/가치) — 분류실패·판단보류는 리포트에서 제외 옵션
    valid_mask = result_df["분류"].isin(["실패수요", "가치수요", "기타", "판단보류"])
    n_valid = int(valid_mask.sum())
    n_fail  = int((result_df["분류"] == "분류실패").sum())

    col_o1, col_o2 = st.columns(2)
    with col_o1:
        quotes_per_sub = st.slider(
            "세부분류별 대표 인용문 수",
            min_value=3, max_value=15, value=8, step=1,
            help="많을수록 근거가 풍부하지만 리포트가 길어집니다.",
        )
    with col_o2:
        period_label = st.text_input(
            "리포트 기간 표기 (선택)",
            value="",
            placeholder="예: 2025-01 ~ 2025-06",
        )

    if n_fail > 0:
        st.caption(f"※ 분류실패 {n_fail:,}건은 리포트에서 자동 제외됩니다. (유효 {n_valid:,}건 대상)")

    # 출처(규칙/LLM) 요약
    if "출처" in result_df.columns:
        src_counts = result_df["출처"].value_counts().to_dict()
        rule_n = src_counts.get("규칙", 0)
        if rule_n:
            st.caption(
                f"⚡ 규칙 사전분류 {rule_n:,}건 / "
                f"LLM {sum(v for k, v in src_counts.items() if k != '규칙'):,}건"
            )

    if st.button("🧭 리포트 생성", type="primary"):
        report_df = result_df[valid_mask].copy()
        with st.spinner("집계 및 개인정보 마스킹 중..."):
            md = rb.build_markdown_report(
                report_df,
                period_label=period_label.strip(),
                quotes_per_sub=int(quotes_per_sub),
            )
            # 마스킹 통계 (안내용)
            from pii import mask_series
            _, masked_count = mask_series(report_df["text"].tolist())
        st.session_state["report_md"] = md
        st.session_state["report_masked_count"] = masked_count
        st.success("리포트가 생성됐습니다. 아래에서 미리보기·다운로드하세요.")

    report_md = st.session_state.get("report_md")
    if report_md:
        masked_count = st.session_state.get("report_masked_count", 0)
        if masked_count:
            st.markdown(
                f'<span class="status-ok">● 개인정보 {masked_count:,}건 마스킹 완료</span> '
                "(전화·이메일·주소·카드·주문번호·이름 등)",
                unsafe_allow_html=True,
            )
        st.warning(
            "⚠️ 규칙 기반 마스킹은 완벽하지 않습니다. 외부 반출 전 미리보기를 훑어보고, "
            "사내 데이터 반출 정책(외부 AI 서비스 업로드 허용 여부)을 반드시 확인하세요."
        )

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "📥 리포트 다운로드 (.md)",
                data=report_md.encode("utf-8"),
                file_name=f"전략리포트_{now_str()}.md",
                mime="text/markdown",
                type="primary",
                use_container_width=True,
            )
        with col_dl2:
            st.download_button(
                "📥 Claude 지침 다운로드 (.txt)",
                data=rb.build_strategy_prompt().encode("utf-8"),
                file_name="claude_전략분석_지침.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with st.expander("📄 리포트 미리보기", expanded=True):
            st.markdown(report_md)

        st.markdown('<div class="section-title">🔗 Claude 프로젝트 사용 방법</div>', unsafe_allow_html=True)
        st.markdown(
            """
1. **Claude 프로젝트 생성** — claude.ai에서 새 프로젝트를 만듭니다.
2. **지식 추가** — 위 `.md` 리포트 파일을 프로젝트 지식(Project knowledge)에 업로드합니다.
3. **커스텀 인스트럭션 설정** — `claude_전략분석_지침.txt` 내용을 프로젝트
   커스텀 인스트럭션에 붙여넣습니다.
4. **단계적 대화** — 한 번에 다 시키지 말고 순서대로 진행하세요:
   `① Pain Point 도출` → (검토·수정) → `② 근본원인` → `③ 개선과제` → `④ 우선순위·로드맵`.
   각 단계 결과를 확인하고 넘어가면 품질이 크게 올라갑니다.

> 사내 정책상 외부 AI 업로드가 어렵다면, 이 리포트를 사내 승인된 LLM 엔드포인트나
> 오프라인 검토 자료로 그대로 활용할 수 있습니다.
"""
        )
        with st.expander("📋 Claude 지침 미리보기"):
            st.code(rb.build_strategy_prompt(), language="text")


# ══════════════════════════════════════════════
# 탭 5 — 도움말
# ══════════════════════════════════════════════
with tab_help:
    st.markdown("## ❓ 도움말 및 오류 해결")

    with st.expander("🚀 처음 설치 방법 (Windows)"):
        st.markdown(
            """
**1단계 — Python 설치**
1. https://www.python.org 에서 Python 3.11 이상을 다운로드해 설치합니다.
2. 설치 시 **"Add Python to PATH"** 옵션을 반드시 체크하세요.

**2단계 — Ollama 설치 및 모델 다운로드**
1. https://ollama.com 에서 Windows용 설치 파일을 다운로드해 실행합니다.
2. 설치 후 터미널에서 (RAM 8GB 미만이면 qwen2.5:3b 권장):
```
ollama pull qwen2.5:3b
```
RAM이 10GB 이상이면 한국어 성능이 더 좋은 exaone3.5 사용 가능:
```
ollama pull exaone3.5
```

**3단계 — 라이브러리 설치**
```
pip install -r requirements.txt
```

**4단계 — DB 접속 정보 설정 (DB 사용 시)**

`.env.example` 파일을 복사 → `.env` 로 이름 변경 → 값 입력.

**5단계 — 실행**
```
ollama serve
streamlit run app.py
```
"""
        )

    with st.expander("🍎 처음 설치 방법 (Mac)"):
        st.markdown(
            """
```bash
brew install python ollama
ollama serve &
ollama pull exaone3.5
pip3 install -r requirements.txt
streamlit run app.py
```
"""
        )

    with st.expander("⚠️ 오류 해결법"):
        st.markdown(
            """
| 오류 상황 | 해결 방법 |
|-----------|-----------|
| "Ollama 미실행" | 터미널에서 `ollama serve` 실행 후 새로고침 |
| 설치된 모델 없음 | `ollama pull qwen2.5:3b` 실행 후 새로고침 |
| **HTTP 500 / RAM 부족** | **`ollama pull qwen2.5:3b` 으로 작은 모델 사용** |
| unable to allocate CPU buffer | RAM 부족. qwen2.5:3b (4GB) 또는 gemma2:2b (3GB) 사용 |
| DB 연결 실패 | .env 파일 접속 정보 확인. 방화벽/VPN 상태 확인 |
| 한글 깨짐 | CSV는 UTF-8 또는 CP949 저장. Excel 사용 권장 |
| JSON 파싱 실패 | 자동 "분류실패" 처리됨. 모델 변경 또는 본문 확인 |
| 분류가 너무 느림 | 더 작은 모델 선택 (qwen2.5:3b, gemma2:2b) |
"""
        )

    with st.expander("🧭 실패수요 vs 가치수요 — 분류 기준"):
        st.markdown(
            """
이 프로그램의 핵심은 고객 문의를 **실패수요**와 **가치수요**로 나누는 것입니다.

#### 판단 공식
> **"회사가 일을 완벽히 했어도 고객이 이 질문을 했을까?"**
> - **예** (사고 싶거나 쓰려고 자연스럽게 묻는 것) → **가치수요**
> - **아니오** (문제·오류·누락 때문에 어쩔 수 없이 묻는 것) → **실패수요**

#### 🟢 가치수요 (회사가 원하는 좋은 수요) — 영업·마케팅 기회
| 세부분류 | 예시 |
|----------|------|
| 구매상담 | 모델 추천, 재입고/구매 가능 여부 |
| 스펙/호환성 | "호환되나요?", 치수·전자파·케이블 규격 |
| 가격/혜택 | "55% 할인 맞나요?", 포인트·캐시백 |
| 설치조건 | "기사님이 전기공사도 해주나요?", 설치비 |
| 사용방법 | 사용법·설정·기능 동작 |
| AS사전문의 | 보증기간·부품 구매 방법 (고장 전) |
| 기타가치 | 색상 옵션·구성품 |

#### 🔴 실패수요 (회사 실패로 생긴 불필요한 수요) — 개선 과제
| 세부분류 | 예시 |
|----------|------|
| 배송지연 | "배송이 너무 늦어요" |
| 오배송/파손 | 다른 물건·파손품 수령 |
| 결제/환불오류 | 결제 실패·환불 지연 |
| 상품정보불일치 | 출시연도·가격이 서로 다르게 표기 |
| 설치/기사미흡 | 기사 미방문·설치 불량 |
| CS응대불만 | 상담 답변이 틀림·서로 다름 |
| AS처리지연 | 제품 고장으로 수리 필요 |
| 시스템오류 | 예약날짜 안뜸, 시리얼 등록 불가 |
| 기타실패 | 그 외 회사 실패 문의 |

#### 헷갈리기 쉬운 경계
- "재입고 되나요?" → 살 의향이 있는 **가치수요(구매상담)** (실패수요 아님)
- "전자파 얼마나 나오나요?" → 제품 사양 확인 **가치수요(스펙)**
- "리모콘이 고장났어요" → 제품 결함 **실패수요(AS처리지연)**
- "예약날짜가 안떠서 구매를 못해요" → 주문 시스템 **실패수요(시스템오류)**

> 결과가 애매하면 3단계 **검토 및 수정** 화면에서 사람이 직접 바로잡을 수 있습니다.
"""
        )

    with st.expander("🧭 전략 리포트 & Claude 프로젝트 연계"):
        st.markdown(
            """
사양이 낮은 PC에서는 로컬 소형 모델로 **분류까지만** 처리하고, Pain Point 도출·전략
수립 같은 **무거운 추론은 Claude 프로젝트**(또는 사내 승인 LLM)에 맡기는 구성이 효율적입니다.

**4단계: 전략 리포트** 탭에서 다음을 자동 생성합니다.
- **집계 리포트(.md)** — 수요 구조, 실패수요 세부분류 순위·심각도, 대표 인용문,
  상품 × 실패 교차표, 월별 추이, 가치수요 기회 요약
- **개인정보 마스킹** — 전화·이메일·주소·카드·주문번호·이름 등을 가림
- **인용문 [ID]** — 각 대표 인용문에 원본 추적용 식별자 부여
- **Claude 지침(.txt)** — 프로젝트 커스텀 인스트럭션에 붙여넣을 분석 지침

**사용 순서**
1. claude.ai에서 새 프로젝트 생성
2. 리포트 `.md`를 프로젝트 지식에 업로드
3. 지침 `.txt` 내용을 커스텀 인스트럭션에 입력
4. `① Pain Point → ② 근본원인 → ③ 개선과제 → ④ 우선순위` 순서로 단계적 대화

> ⚠️ 규칙 기반 마스킹은 완벽하지 않습니다. 외부 반출 전 리포트를 확인하고,
> 사내 데이터 반출 정책을 반드시 준수하세요. 외부 업로드가 어렵다면 사내 승인
> LLM이나 오프라인 검토 자료로 그대로 활용할 수 있습니다.

**⚡ 규칙 사전분류란?**
배송지연·환불오류·시스템오류·파손·호환성처럼 표현이 아주 명확한 문의는 LLM을
호출하지 않고 규칙으로 즉시 분류합니다. 저사양 PC에서 처리 시간을 크게 줄일 수
있으며, 결과의 **출처** 열에서 `규칙`/`LLM`을 구분할 수 있습니다. 애매한 문의는
규칙에 넣지 않고 LLM으로 넘겨 정확도를 유지합니다.
"""
        )

    with st.expander("🗄️ IT/DBA에 요청할 DB 체크리스트"):
        st.markdown(
            """
1. Redshift 호스트 주소 (RS_HOST)
2. 포트 번호 (RS_PORT, 기본 5439)
3. 데이터베이스 이름 (RS_DATABASE)
4. **읽기 전용 계정** 아이디/비밀번호 (RS_USER / RS_PASSWORD)
5. Q&A 데이터 테이블명·컬럼명 (본문 / 작성일 / 상품명 / 고유ID)
6. 리뷰 데이터 테이블명·컬럼명
7. Cloud PC IP 등록 필요 여부
"""
        )

    with st.expander("🔒 보안 안내"):
        st.markdown(
            """
- 비밀번호는 **.env 파일에만** 보관하세요. 이메일·코드·메신저에 절대 포함하지 마세요.
- `.env` 파일은 절대 GitHub/공유 폴더에 올리지 마세요. (.gitignore에 자동 포함됨)
- 이 프로그램은 DB에서 **읽기(SELECT)만** 수행합니다. 데이터를 수정·삭제하지 않습니다.
- Ollama 로컬 LLM을 사용하므로 고객 데이터가 외부로 전송되지 않습니다.
"""
        )
