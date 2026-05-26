"""
공통 유틸리티 — 인코딩 처리, 세션 저장/불러오기, Excel 출력
"""

import io
import json
import pickle
import datetime
from pathlib import Path
from typing import Optional

import chardet
import pandas as pd


CHECKPOINT_PATH = Path("checkpoint_progress.pkl")

CATEGORY_LABELS = {
    "실패수요": "🔴 실패수요",
    "가치수요": "🟢 가치수요",
    "기타": "⚪ 기타",
    "판단보류": "🟡 판단보류",
    "분류실패": "❌ 분류실패",
}

CATEGORY_COLORS = {
    "실패수요": "#F2738C",
    "가치수요": "#6FCF97",
    "기타": "#9AA6B3",
    "판단보류": "#F0B65E",
    "분류실패": "#677483",
}


def detect_encoding(raw: bytes) -> str:
    result = chardet.detect(raw)
    enc = result.get("encoding") or "utf-8"
    # CP949 / EUC-KR 계열 통일
    if enc.lower() in ("euc-kr", "euc_kr", "cp949"):
        enc = "cp949"
    return enc


def read_csv_auto(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.read()
    enc = detect_encoding(raw)
    try:
        df = pd.read_csv(io.BytesIO(raw), encoding=enc)
    except Exception:
        df = pd.read_csv(io.BytesIO(raw), encoding="utf-8", errors="replace")
    return df


def read_excel_auto(uploaded_file) -> pd.DataFrame:
    return pd.read_excel(uploaded_file, engine="openpyxl")


def save_checkpoint(data: dict) -> None:
    with open(CHECKPOINT_PATH, "wb") as f:
        pickle.dump(data, f)


def load_checkpoint() -> Optional[dict]:
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, "rb") as f:
            return pickle.load(f)
    return None


def clear_checkpoint() -> None:
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="분류결과")
        workbook = writer.book
        worksheet = writer.sheets["분류결과"]

        # 열 너비 자동 조정
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(str(col))) + 4
            worksheet.set_column(i, i, min(max_len, 60))

        # 분류 컬럼 조건부 색상
        if "분류" in df.columns:
            col_idx = df.columns.get_loc("분류")
            color_map = {
                "실패수요": "#FDDDE6",
                "가치수요": "#D4EDDA",
                "기타": "#E9ECEF",
                "판단보류": "#FFF3CD",
                "분류실패": "#DEE2E6",
            }
            for cat, bg in color_map.items():
                fmt = workbook.add_format({"bg_color": bg})
                for row_idx, val in enumerate(df["분류"], start=1):
                    if val == cat:
                        worksheet.write(row_idx, col_idx, val, fmt)

    return buf.getvalue()


def now_str() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_json_parse(text: str) -> Optional[dict]:
    """LLM 응답에서 JSON 부분만 추출해 파싱"""
    text = text.strip()
    # 코드블록 제거
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    # 중괄호 범위 추출
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
