"""공통 유틸리티 함수."""

from __future__ import annotations

import io

import pandas as pd

from .query_builder import RESULT_COLUMNS


def load_sample_dataframe(file) -> pd.DataFrame:
    """CSV/TSV 업로드를 7개 컬럼 DataFrame으로 로드한다(대체 모드, PRD 15).

    Redshift 접근이 어려운 환경에서 샘플 파일로 점검을 진행하기 위한 경로.
    """
    if hasattr(file, "read"):
        raw = file.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")
        buffer = io.StringIO(raw)
    else:
        buffer = file

    # 구분자 자동 추정
    sample = buffer.read(4096)
    buffer.seek(0)
    sep = "\t" if sample.count("\t") > sample.count(",") else ","
    df = pd.read_csv(buffer, sep=sep, dtype=str)

    for col in RESULT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[RESULT_COLUMNS]


def make_sample_dataframe() -> pd.DataFrame:
    """테스트/데모용 샘플 데이터를 생성한다."""
    data = [
        # 정상 PDP
        ("12인용", "주방가전", "냉장고", "12인용", "DUE4BGE.AKOR",
         "https://www.lge.co.kr/refrigerators/h875gga031", "냉장고|상세"),
        ("14인용", "주방가전", "냉장고", "14인용", "DFB22PR.AKOR",
         "https://www.lge.co.kr/dishwashers/dfb22pr", "식기세척기|상세"),
        # 카테고리 URL → EXCLUDED
        ("냉장고", "주방가전", "냉장고", "", "CATG001",
         "https://www.lge.co.kr/category/refrigerators", "냉장고|카테고리"),
        # 모바일 카테고리 URL → EXCLUDED
        ("냉장고", "주방가전", "냉장고", "", "CATG002",
         "https://www.lge.co.kr/m/category/refrigerators", "냉장고|모바일카테고리"),
        # 스토어 URL → EXCLUDED
        ("스토어", "스토어", "스토어", "", "STORE001",
         "https://www.lge.co.kr/store/event", "스토어|이벤트"),
    ]
    return pd.DataFrame(data, columns=RESULT_COLUMNS)
