"""
고객 문의·리뷰 자동 분류 프로그램
LGE.COM CS 전략 과제 — Ollama 로컬 LLM + Amazon Redshift
"""

import random
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import classifier as clf
import data_loader as dl
import db_connector as dbc
from utils import (
    CATEGORY_COLORS,
    CATEGORY_LABELS,
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
# CSS 커스텀
# ─────────────────────────────────────────────
st.markdown(
    """
<style>
    .stApp { background-color: #0f1117; }
    .metric-card {
        background: #1a2029; border: 1px solid #2a323d;
        border-radius: 10px; padding: 16px 20px; text-align: center;
    }
    .metric-card .label { font-size: 13px; color: #9aa6b3; margin-bottom: 6px; }
    .metric-card .value { font-size: 28px; font-weight: 800; color: #ffffff; }
    .metric-card .pct   { font-size: 14px; color: #677483; margin-top: 4px; }
    .section-title {
        font-size: 18px; font-weight: 700; color: #ffffff;
        border-left: 3px solid #4fd1c5; padding-left: 12px; margin: 24px 0 12px;
    }
    .info-box {
        background: #1a2029; border: 1px solid #2a323d;
        border-radius: 8px; padding: 14px 18px; font-size: 14px; color: #9aa6b3;
    }
    .status-ok   { color: #6fcf97; font-weight: 700; }
    .status-warn { color: #f0b65e; font-weight: 700; }
    .status-err  { color: #f2738c; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────
def _init_state():
    defaults = {
        "standard_df": None,       # 표준화된 입력 데이터
        "result_df": None,         # 분류 완료 결과
        "is_running": False,       # 분류 실행 중 여부
        "stop_flag": [False],      # 중단 플래그
        "db_conn": None,           # DB 연결 객체
        "db_driver": None,
        "selected_model": None,
        "progress_current": 0,
        "progress_total": 0,
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
    st.markdown("---")

    # Ollama 상태 점검
    st.markdown("### ⚙️ LLM 엔진 상태")
    ollama_ok, ollama_msg = clf.check_ollama()
    if ollama_ok:
        st.markdown(f'<span class="status-ok">● Ollama 실행 중</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="status-err">● Ollama 미실행</span>', unsafe_allow_html=True)
        st.error(ollama_msg)
        st.markdown(
            "**Ollama 시작 방법:**\n\n"
            "터미널(명령 프롬프트)에서:\n"
            "```\nollama serve\n```"
        )

    # 모델 선택
    models = clf.list_models()
    if models:
        preferred = [m for m in models if any(k in m for k in ["exaone", "qwen", "gemma"])]
        ordered = preferred + [m for m in models if m not in preferred]
        selected_model = st.selectbox("🤖 분류 모델 선택", ordered)
        st.session_state["selected_model"] = selected_model
        st.markdown(
            '<div class="info-box">'
            "<b>모델 추천 순서:</b><br>"
            "① exaone3.5 (한국어 최우수 · LG AI연구원)<br>"
            "② qwen2.5 (다국어 강함)<br>"
            "③ gemma2 (경량 · 저사양 PC용)"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("설치된 모델이 없습니다.")
        st.markdown(
            "아래 명령어로 모델을 설치하세요:\n"
            "```\nollama pull exaone3.5\n```"
            "또는\n"
            "```\nollama pull qwen2.5:7b\n```"
        )
        st.session_state["selected_model"] = None

    st.markdown("---")

    # 중간 저장 불러오기
    checkpoint = load_checkpoint()
    if checkpoint:
        st.markdown("### 💾 이전 작업 발견")
        saved_at = checkpoint.get("saved_at", "알 수 없음")
        saved_count = checkpoint.get("processed_count", 0)
        st.info(f"저장 시각: {saved_at}\n처리 완료: {saved_count:,}건")
        col_resume, col_discard = st.columns(2)
        with col_resume:
            if st.button("▶ 이어하기", use_container_width=True):
                st.session_state["standard_df"] = checkpoint.get("standard_df")
                st.session_state["result_df"] = checkpoint.get("result_df")
                st.rerun()
        with col_discard:
            if st.button("🗑 버리기", use_container_width=True):
                clear_checkpoint()
                st.rerun()


# ─────────────────────────────────────────────
# 메인 영역
# ─────────────────────────────────────────────
st.markdown("# 🔍 고객 문의·리뷰 자동 분류 프로그램")
st.markdown(
    "고객 Q&A 및 상품 리뷰를 **실패수요 / 가치수요 / 기타 / 판단보류**로 자동 분류합니다. "
    "분류에는 사내 Ollama 로컬 LLM을 사용하므로 외부 인터넷 없이 동작합니다."
)

tab_input, tab_classify, tab_result, tab_help = st.tabs(
    ["📂 1단계: 데이터 입력", "▶ 2단계: 분류 실행", "📊 3단계: 결과·검토", "❓ 도움말"]
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
                    st.session_state["result_df"] = None
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
                    st.session_state["db_conn"] = conn
                    st.session_state["db_driver"] = driver
                    st.success(msg)
                else:
                    st.error(msg)

            if st.session_state["db_conn"]:
                df = dl.load_from_db(st.session_state["db_conn"], data_type)
                if df is not None and len(df) > 0:
                    st.success(f"✅ {len(df):,}건 로드 완료")
                    if st.button("💾 이 데이터로 분류 준비 완료", type="primary", key="db_ready"):
                        st.session_state["standard_df"] = df
                        st.session_state["result_df"] = None
                        clear_checkpoint()
                        st.success("2단계 탭에서 분류를 시작할 수 있습니다.")


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

    # 이미 완료된 결과가 있는 경우
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

        st.markdown("---")

        # 샘플 검증
        st.markdown("### 🔬 샘플 검증 (권장)")
        st.markdown(
            "전체 분류 전에 소량 샘플로 품질을 먼저 확인하는 것을 **강력히 권장**합니다. "
            "샘플 결과를 보고 분류 기준을 조정한 뒤 전체를 실행하세요."
        )
        sample_size = st.number_input(
            "샘플 건수", min_value=10, max_value=min(500, len(std_df)), value=min(100, len(std_df)), step=10
        )
        if st.button("🔬 샘플 검증 시작", disabled=not model):
            sample_indices = random.sample(range(len(std_df)), int(sample_size))
            sample_df = std_df.iloc[sample_indices].copy().reset_index(drop=True)

            progress_bar = st.progress(0, text="샘플 분류 중...")
            status_text = st.empty()

            results = []
            for i, row in sample_df.iterrows():
                result = clf.classify_one(row["text"], model)
                results.append(result)
                pct = (i + 1) / len(sample_df)
                progress_bar.progress(pct, text=f"샘플 분류 중... {i+1}/{len(sample_df)}")
                status_text.text(f"최근 분류: [{result['분류']}] {row['text'][:50]}...")

            result_records = pd.DataFrame(results)
            sample_result = pd.concat([sample_df.reset_index(drop=True), result_records], axis=1)
            st.session_state["sample_result"] = sample_result
            progress_bar.empty()
            status_text.empty()
            st.success("샘플 분류 완료!")

        sample_result = st.session_state.get("sample_result")
        if sample_result is not None:
            st.markdown("**샘플 분류 결과**")
            counts = sample_result["분류"].value_counts()
            c1, c2, c3, c4 = st.columns(4)
            for col_w, cat in zip([c1, c2, c3, c4], ["실패수요", "가치수요", "기타", "판단보류"]):
                with col_w:
                    n = counts.get(cat, 0)
                    pct = n / len(sample_result) * 100
                    color = CATEGORY_COLORS.get(cat, "#fff")
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="label">{CATEGORY_LABELS[cat]}</div>'
                        f'<div class="value" style="color:{color}">{n}</div>'
                        f'<div class="pct">{pct:.1f}%</div></div>',
                        unsafe_allow_html=True,
                    )

            st.dataframe(
                sample_result[["text", "분류", "세부사유", "확신도"]].head(20),
                use_container_width=True,
            )

        st.markdown("---")

        # 전체 분류
        st.markdown("### ▶ 전체 분류 실행")
        btn_col1, btn_col2 = st.columns([2, 1])
        with btn_col1:
            run_btn = st.button(
                f"▶ 전체 분류 시작 ({len(std_df):,}건)",
                type="primary",
                disabled=not model or st.session_state["is_running"],
            )
        with btn_col2:
            stop_btn = st.button(
                "⏹ 중단",
                disabled=not st.session_state["is_running"],
            )

        if stop_btn:
            st.session_state["stop_flag"][0] = True
            st.warning("중단 요청됨. 현재 처리 중인 건이 완료되면 멈춥니다.")

        if run_btn and not st.session_state["is_running"]:
            st.session_state["is_running"] = True
            st.session_state["stop_flag"] = [False]
            results_so_far = []

            progress_bar = st.progress(0, text="분류 준비 중...")
            status_text = st.empty()
            elapsed_text = st.empty()
            start_time = time.time()

            def on_progress(current, total):
                pct = current / total
                elapsed = time.time() - start_time
                rate = current / elapsed if elapsed > 0 else 0
                remaining = (total - current) / rate if rate > 0 else 0
                progress_bar.progress(
                    pct,
                    text=f"분류 중... {current:,}/{total:,}건 ({pct*100:.1f}%)",
                )
                elapsed_text.text(
                    f"경과: {elapsed:.0f}초 | 남은 예상 시간: {remaining:.0f}초 | 속도: {rate:.1f}건/초"
                )

            def on_checkpoint(partial_results):
                partial_df_res = pd.DataFrame(partial_results)
                partial_std = std_df.iloc[: len(partial_results)].copy().reset_index(drop=True)
                partial_merged = pd.concat([partial_std, partial_df_res], axis=1)
                save_checkpoint(
                    {
                        "standard_df": std_df,
                        "result_df": partial_merged,
                        "processed_count": len(partial_results),
                        "saved_at": now_str(),
                    }
                )

            texts = std_df["text"].tolist()
            raw_results = clf.classify_batch(
                texts,
                model,
                progress_callback=on_progress,
                stop_flag=st.session_state["stop_flag"],
                checkpoint_callback=on_checkpoint,
                checkpoint_interval=int(checkpoint_interval),
            )

            result_records = pd.DataFrame(raw_results)
            processed_std = std_df.iloc[: len(raw_results)].copy().reset_index(drop=True)
            final_df = pd.concat([processed_std, result_records], axis=1)
            final_df["검토완료"] = False

            st.session_state["result_df"] = final_df
            st.session_state["is_running"] = False
            st.session_state["confidence_threshold"] = confidence_threshold
            clear_checkpoint()

            progress_bar.empty()
            status_text.empty()
            elapsed_text.empty()

            total_time = time.time() - start_time
            stopped = st.session_state["stop_flag"][0]
            if stopped:
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

    # ── 요약 지표 ──
    st.markdown('<div class="section-title">📊 분류 결과 요약</div>', unsafe_allow_html=True)
    total = len(result_df)
    counts = result_df["분류"].value_counts()

    metric_cols = st.columns(5)
    for i, (cat, label) in enumerate(CATEGORY_LABELS.items()):
        n = counts.get(cat, 0)
        pct = n / total * 100 if total > 0 else 0
        color = CATEGORY_COLORS.get(cat, "#fff")
        with metric_cols[i]:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="label">{label}</div>'
                f'<div class="value" style="color:{color}">{n:,}</div>'
                f'<div class="pct">{pct:.1f}%</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(f"<br>**전체:** {total:,}건", unsafe_allow_html=True)

    # ── 차트 ──
    st.markdown('<div class="section-title">📈 차트</div>', unsafe_allow_html=True)
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        pie_data = pd.DataFrame(
            {"분류": list(CATEGORY_LABELS.keys()), "건수": [counts.get(c, 0) for c in CATEGORY_LABELS]}
        )
        pie_data = pie_data[pie_data["건수"] > 0]
        fig_pie = px.pie(
            pie_data, names="분류", values="건수",
            color="분류",
            color_discrete_map=CATEGORY_COLORS,
            title="분류 비율",
        )
        fig_pie.update_layout(paper_bgcolor="#0f1117", plot_bgcolor="#0f1117", font_color="#d7dee7")
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        # 세부사유 Top 10
        fd = result_df[result_df["분류"] == "실패수요"]
        if len(fd) > 0 and "세부사유" in fd.columns:
            top_reasons = fd["세부사유"].value_counts().head(10).reset_index()
            top_reasons.columns = ["세부사유", "건수"]
            fig_bar = px.bar(
                top_reasons, x="건수", y="세부사유", orientation="h",
                title="실패수요 세부사유 Top 10",
                color_discrete_sequence=["#F2738C"],
            )
            fig_bar.update_layout(
                paper_bgcolor="#0f1117", plot_bgcolor="#1a2029",
                font_color="#d7dee7", yaxis={"autorange": "reversed"},
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("실패수요 데이터가 없어 세부사유 차트를 표시할 수 없습니다.")

    # 기간별 추이 (날짜 있는 경우)
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
                    color_discrete_map=CATEGORY_COLORS,
                    title="월별 분류 추이",
                    markers=True,
                )
                fig_trend.update_layout(
                    paper_bgcolor="#0f1117", plot_bgcolor="#1a2029", font_color="#d7dee7"
                )
                st.plotly_chart(fig_trend, use_container_width=True)
        except Exception:
            pass

    # ── 검토·수정 표 ──
    st.markdown('<div class="section-title">🔎 검토 및 수정</div>', unsafe_allow_html=True)

    review_filter = st.radio(
        "표시 필터",
        ["전체", f"확신도 낮음 ({confidence_threshold} 미만)", "실패수요", "가치수요", "기타", "판단보류", "분류실패"],
        horizontal=True,
    )

    filtered = result_df.copy()
    if review_filter == f"확신도 낮음 ({confidence_threshold} 미만)":
        filtered = filtered[filtered["확신도"].astype(float) < confidence_threshold]
    elif review_filter in ["실패수요", "가치수요", "기타", "판단보류", "분류실패"]:
        filtered = filtered[filtered["분류"] == review_filter]

    st.markdown(f"표시 중: **{len(filtered):,}건**")

    # 수정 가능한 표
    category_options = ["실패수요", "가치수요", "기타", "판단보류", "분류실패"]
    display_cols = ["inquiry_id", "data_type", "text", "분류", "세부사유", "확신도"]
    available_cols = [c for c in display_cols if c in filtered.columns]

    if len(filtered) > 0:
        edited_df = st.data_editor(
            filtered[available_cols],
            column_config={
                "분류": st.column_config.SelectboxColumn(
                    "분류", options=category_options, required=True
                ),
                "text": st.column_config.TextColumn("본문", width="large"),
                "확신도": st.column_config.NumberColumn("확신도", min_value=0, max_value=100, format="%d"),
                "inquiry_id": st.column_config.TextColumn("ID", width="small"),
                "data_type": st.column_config.TextColumn("유형", width="small"),
                "세부사유": st.column_config.TextColumn("세부사유", width="medium"),
            },
            use_container_width=True,
            num_rows="fixed",
            key="review_editor",
        )

        if st.button("💾 수정 내용 반영"):
            for idx, row in edited_df.iterrows():
                orig_idx = filtered.index[list(filtered.index).index(idx)] if idx in filtered.index else None
                if orig_idx is not None:
                    st.session_state["result_df"].at[orig_idx, "분류"] = row["분류"]
            st.success("수정 내용이 결과에 반영됐습니다.")
            st.rerun()
    else:
        st.info("해당 필터에 맞는 항목이 없습니다.")

    # ── 다운로드 ──
    st.markdown('<div class="section-title">📥 결과 다운로드</div>', unsafe_allow_html=True)
    final = st.session_state["result_df"]
    excel_bytes = to_excel_bytes(final)
    filename = f"분류결과_{now_str()}.xlsx"
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
# 탭 4 — 도움말
# ══════════════════════════════════════════════
with tab_help:
    st.markdown("## ❓ 도움말 및 오류 해결")

    with st.expander("🚀 처음 설치 방법 (Windows)"):
        st.markdown(
            """
**1단계 — Python 설치**
1. https://www.python.org 에서 Python 3.11 이상을 다운로드해 설치합니다.
2. 설치 시 **"Add Python to PATH"** 옵션을 반드시 체크하세요.

**2단계 — Ollama 설치**
1. https://ollama.com 에서 Windows용 설치 파일을 다운로드해 실행합니다.
2. 설치 후 터미널에서:
```
ollama pull exaone3.5
```
(사양이 낮으면: `ollama pull qwen2.5:7b` 또는 `ollama pull gemma2`)

**3단계 — 프로그램 라이브러리 설치**

터미널에서 프로그램 폴더로 이동 후:
```
pip install -r requirements.txt
```

**4단계 — DB 접속 정보 설정 (DB 사용 시)**

`.env.example` 파일을 복사해 `.env` 파일로 이름 변경 후 값 입력.

**5단계 — 프로그램 실행**
```
streamlit run app.py
```
"""
        )

    with st.expander("🍎 처음 설치 방법 (Mac)"):
        st.markdown(
            """
**1단계 — Python 설치**
터미널에서:
```
brew install python
```
(Homebrew 없으면: https://brew.sh 설치 후 위 명령 실행)

**2단계 — Ollama 설치**
```
brew install ollama
ollama serve &
ollama pull exaone3.5
```

**3단계 — 라이브러리 설치**
```
pip3 install -r requirements.txt
```

**4단계 — 실행**
```
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
| "설치된 모델이 없습니다" | `ollama pull exaone3.5` 실행 후 새로고침 |
| DB 연결 실패 | .env 파일의 접속 정보 확인. 방화벽/VPN 상태 확인. IT/DBA 문의 |
| 한글 깨짐 | CSV는 UTF-8 또는 CP949로 저장. Excel 사용 권장 |
| JSON 파싱 실패 | 자동으로 "분류실패" 처리됨. 모델 변경 또는 본문 확인 |
| 분류가 너무 느림 | 더 작은 모델 선택 (예: gemma2). GPU 있는 PC 권장 |
| "pip 명령어를 찾을 수 없음" | Python 설치 시 PATH 체크 여부 확인. `pip3` 사용 |
"""
        )

    with st.expander("🗄️ IT/DBA에 요청할 DB 체크리스트"):
        st.markdown(
            """
DB 연결을 위해 아래 정보를 사내 IT부서 또는 DBA에 요청하세요.

**요청 항목:**
1. Redshift 호스트 주소 (RS_HOST)
2. 포트 번호 (RS_PORT, 기본 5439)
3. 데이터베이스 이름 (RS_DATABASE)
4. **읽기 전용 계정** 아이디/비밀번호 (RS_USER / RS_PASSWORD)
   - 운영 계정 사용은 보안 위험이 있으므로 반드시 분석 전용 읽기 전용 계정을 발급받으세요.
5. 고객 Q&A 데이터 테이블명·컬럼명
   - 본문 컬럼, 작성일 컬럼, 상품명 컬럼, 고유ID 컬럼
6. 상품 리뷰 데이터 테이블명·컬럼명 (위와 동일)
7. 접속 허용 IP 등록 필요 시 → 현재 Cloud PC IP 제공 필요
"""
        )

    with st.expander("🔒 보안 안내"):
        st.markdown(
            """
- **비밀번호는 .env 파일에만** 보관하세요. 코드·이메일·메신저·문서에 절대 포함하지 마세요.
- `.env` 파일은 절대 GitHub/공유 폴더에 올리지 마세요. (.gitignore에 자동 포함됨)
- 분석이 끝나면 분석용 계정 비밀번호를 주기적으로 변경하세요.
- 이 프로그램은 DB에서 **읽기(SELECT)만** 수행합니다. 데이터를 수정·삭제하지 않습니다.
- Ollama 로컬 LLM을 사용하므로 고객 데이터가 외부로 전송되지 않습니다.
"""
        )

    with st.expander("💡 분류 품질 향상 팁"):
        st.markdown(
            """
1. **샘플 검증 먼저** — 전체 분류 전 100~500건 샘플로 품질을 확인하세요.
2. **확신도 낮음 필터** — 확신도 75 미만 항목은 사람이 직접 검토하세요.
3. **모델 선택** — 한국어 품질 순서: exaone3.5 > qwen2.5 > gemma2
4. **본문 정제** — 너무 짧거나(1~2글자) 의미 없는 행은 미리 제거하면 정확도가 높아집니다.
5. **재분류** — "분류실패" 항목은 모델 변경 후 다시 시도해보세요.
"""
        )
