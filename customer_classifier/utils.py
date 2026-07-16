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

# ── 실패수요 세부분류 ──────────────────────────────────────────
# 9개 항목 — 각각 독립적인 개선 과제로 연결 가능
FAILURE_SUBCATEGORIES: dict[str, str] = {
    "배송지연":       "배송 지연·추적 불가",
    "오배송/파손":    "오배송·상품 파손",
    "결제/환불오류":  "결제 오류·환불 지연",
    "상품정보불일치": "상품 설명·사진·스펙 불일치",
    "설치/기사미흡":  "설치 기사 미방문·설치 불량",
    "CS응대불만":     "상담사 응대 불만·답변 지연",
    "AS처리지연":     "A/S 접수·처리·수리 지연",
    "시스템오류":     "앱·웹·주문 시스템 오류",
    "기타실패":       "기타 실패수요",
}

# ── 가치수요 세부분류 ──────────────────────────────────────────
# 7개 항목 — 영업·마케팅·상품 기획 과제로 연결 가능
VALUE_SUBCATEGORIES: dict[str, str] = {
    "구매상담":    "모델 추천·구매 의향 상담",
    "스펙/호환성": "사이즈·스펙·호환성 문의",
    "가격/혜택":   "할인·쿠폰·포인트·멤버십 문의",
    "설치조건":    "설치 가능 여부·조건·비용 문의",
    "사용방법":    "제품 사용법·설정·기능 문의",
    "AS사전문의":  "보증 기간·A/S 절차 사전 확인",
    "기타가치":    "기타 가치수요",
}

ALL_SUBCATEGORIES: dict[str, str] = {
    **FAILURE_SUBCATEGORIES,
    **VALUE_SUBCATEGORIES,
    "해당없음": "해당 없음",
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

        # 열 너비 자동 조정 (None/NaN 섞인 컬럼도 안전하게)
        for i, col in enumerate(df.columns):
            try:
                content_max = int(df[col].map(lambda v: len(str(v)) if v is not None else 0).max())
            except (TypeError, ValueError):
                content_max = 10
            max_len = max(content_max, len(str(col))) + 4
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
                fmt = workbook.add_format({"bg_color": bg, "border": 1})
                for row_idx, val in enumerate(df["분류"], start=1):
                    if val == cat:
                        worksheet.write(row_idx, col_idx, val, fmt)

        # 세부분류 컬럼 색상 (실패수요계 연분홍, 가치수요계 연녹색)
        if "세부분류" in df.columns and "분류" in df.columns:
            sub_col_idx = df.columns.get_loc("세부분류")
            fmt_fail = workbook.add_format({"bg_color": "#FFF0F3", "border": 1})
            fmt_val  = workbook.add_format({"bg_color": "#F0FFF4", "border": 1})
            for row_idx, (cat, sub) in enumerate(zip(df["분류"], df["세부분류"]), start=1):
                if cat == "실패수요":
                    worksheet.write(row_idx, sub_col_idx, sub, fmt_fail)
                elif cat == "가치수요":
                    worksheet.write(row_idx, sub_col_idx, sub, fmt_val)

    return buf.getvalue()


def now_str() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _first_json_object(text: str) -> Optional[str]:
    """첫 번째 '{' 부터 짝이 맞는 '}' 까지의 완전한 JSON 객체 문자열을 반환.
    뒤에 깨진 텍스트(예: '}, "확신도":85}')가 붙어 있어도 올바른 객체만 잘라낸다."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
        elif not in_str:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


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
    # 1) 짝이 맞는 첫 객체 추출 시도 (뒤쪽 깨진 텍스트 무시)
    obj = _first_json_object(text)
    if obj:
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    # 2) 마지막 수단: 처음 '{' ~ 마지막 '}'
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None
