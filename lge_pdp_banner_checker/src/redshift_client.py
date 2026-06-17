"""Redshift 접속 및 쿼리 실행 모듈.

redshift_connector를 사용해 named parameter 쿼리를 실행하고
결과를 pandas DataFrame으로 반환한다. 접속/조회 실패는
사용자 친화적 메시지를 담은 RedshiftError로 변환한다(FR-001).
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from .config import RedshiftConfig
from .query_builder import RESULT_COLUMNS, SKU_PAGE_QUERY, build_query_params


class RedshiftError(Exception):
    """Redshift 접속/조회 단계에서 발생하는 사용자 노출용 오류."""


# :name 형태의 named parameter를 추출하기 위한 정규식
_NAMED_PARAM_RE = re.compile(r":(\w+)")


def _to_paramstyle(sql: str, params: dict) -> tuple[str, list]:
    """`:name` named parameter를 redshift_connector의 `%s` 스타일로 변환한다.

    redshift_connector는 기본적으로 `format`/`pyformat` paramstyle을
    사용하므로 PRD가 요구하는 named parameter 표기를 내부에서 위치
    파라미터로 안전하게 치환한다(값은 바인딩으로 전달 → SQL 인젝션 방지).
    """
    ordered_values: list = []

    def _replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in params:
            raise RedshiftError(f"쿼리 파라미터 누락: :{name}")
        ordered_values.append(params[name])
        return "%s"

    converted = _NAMED_PARAM_RE.sub(_replace, sql)
    return converted, ordered_values


class RedshiftClient:
    """Redshift 접속 래퍼."""

    def __init__(self, config: RedshiftConfig):
        self.config = config

    def _connect(self):
        try:
            import redshift_connector
        except ImportError as exc:  # pragma: no cover - 환경 의존
            raise RedshiftError(
                "redshift-connector 패키지가 설치되어 있지 않습니다. "
                "`pip install -r requirements.txt`를 실행하세요."
            ) from exc

        if not self.config.is_complete():
            missing = ", ".join(self.config.missing_fields())
            raise RedshiftError(
                f"Redshift 접속 정보가 부족합니다. .env에서 다음 값을 확인하세요: {missing}"
            )

        try:
            return redshift_connector.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                ssl=self.config.ssl,
            )
        except Exception as exc:  # noqa: BLE001 - 다양한 드라이버 예외 통합
            raise RedshiftError(
                "Redshift 접속에 실패했습니다. 호스트/포트/계정/네트워크 설정을 "
                f"확인하세요. (원인: {exc})"
            ) from exc

    def test_connection(self) -> bool:
        """접속 가능 여부를 확인한다. 실패 시 RedshiftError를 발생시킨다."""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        finally:
            conn.close()

    def query(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """named parameter 쿼리를 실행하고 DataFrame을 반환한다."""
        params = params or {}
        converted_sql, values = _to_paramstyle(sql, params)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(converted_sql, values)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
            return pd.DataFrame(rows, columns=columns)
        except RedshiftError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RedshiftError(
                f"쿼리 실행에 실패했습니다. (원인: {exc})"
            ) from exc
        finally:
            conn.close()

    def fetch_sku_pages(
        self, start_date, end_date
    ) -> pd.DataFrame:
        """기간 기준 SKU/PDP 후보 7개 컬럼을 조회한다(PRD 6.3)."""
        params = build_query_params(start_date, end_date)
        df = self.query(SKU_PAGE_QUERY, params)
        # 컬럼 순서/존재 보장
        for col in RESULT_COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        return df[RESULT_COLUMNS]
