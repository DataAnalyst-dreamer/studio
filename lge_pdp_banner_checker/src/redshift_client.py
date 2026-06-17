"""Redshift 접속 및 쿼리 실행 모듈.

redshift_connector를 사용해 named parameter 쿼리를 실행하고
결과를 pandas DataFrame으로 반환한다. 접속/조회 실패는
사용자 친화적 메시지를 담은 RedshiftError로 변환한다(FR-001).
"""

from __future__ import annotations

import contextlib
import os
import re
import ssl as _ssl
from typing import Optional

import pandas as pd

from .config import RedshiftConfig
from .query_builder import RESULT_COLUMNS, SKU_PAGE_QUERY, build_query_params


class RedshiftError(Exception):
    """Redshift 접속/조회 단계에서 발생하는 사용자 노출용 오류."""


class _InsecureSSLContext(_ssl.SSLContext):
    """인증서 검증을 강제로 비활성화하는 SSLContext.

    redshift_connector는 sslmode가 verify-ca/verify-full일 때 항상
    CERT_REQUIRED로 검증한다. 사내 TLS 가로채기(self-signed 체인) 환경에서
    QA 점검을 진행할 수 있도록, 검증 관련 속성 변경을 무력화한다.
    암호화는 유지되나 서버 신원 검증은 수행하지 않는다(운영 비권장).
    """

    def __setattr__(self, name, value):
        # verify_mode/check_hostname 변경 시도를 무시한다. 새로 생성된
        # SSLContext의 보안 기본값(CERT_NONE, check_hostname=False)을 유지하여
        # 검증을 비활성화한다. (base setter를 호출하지 않아 재귀를 피한다.)
        if name in ("verify_mode", "check_hostname"):
            return
        super().__setattr__(name, value)

    def load_verify_locations(self, *args, **kwargs):  # noqa: D401
        return None


@contextlib.contextmanager
def _insecure_ssl_patch():
    """`ssl.SSLContext`를 임시로 검증 비활성 컨텍스트로 교체한다."""
    original = _ssl.SSLContext
    _ssl.SSLContext = _InsecureSSLContext  # type: ignore[misc]
    try:
        yield
    finally:
        _ssl.SSLContext = original  # type: ignore[misc]


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

        # 사내 루트 CA 번들이 지정되면 신뢰 저장소에 반영(검증 유지).
        if self.config.ssl and self.config.ca_bundle:
            if not os.path.isfile(self.config.ca_bundle):
                raise RedshiftError(
                    f"REDSHIFT_CA_BUNDLE 경로를 찾을 수 없습니다: {self.config.ca_bundle}"
                )
            os.environ["SSL_CERT_FILE"] = self.config.ca_bundle

        connect_kwargs = dict(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            ssl=self.config.ssl,
        )
        if self.config.ssl:
            connect_kwargs["sslmode"] = self.config.sslmode

        try:
            if self.config.ssl and self.config.ssl_insecure:
                # 검증 비활성(자가서명 체인 우회). 암호화는 유지.
                with _insecure_ssl_patch():
                    return redshift_connector.connect(**connect_kwargs)
            return redshift_connector.connect(**connect_kwargs)
        except Exception as exc:  # noqa: BLE001 - 다양한 드라이버 예외 통합
            hint = ""
            if "CERTIFICATE_VERIFY_FAILED" in str(exc) or "self-signed" in str(exc):
                hint = (
                    " SSL 인증서 검증 실패입니다. 사내 보안장비의 TLS 가로채기일 수 "
                    "있습니다. 사내 루트 CA를 REDSHIFT_CA_BUNDLE로 지정하거나, "
                    "임시로 REDSHIFT_SSL_INSECURE=true(검증 우회) 또는 "
                    "REDSHIFT_SSL=false(평문, 클러스터가 허용 시)로 시도하세요."
                )
            raise RedshiftError(
                "Redshift 접속에 실패했습니다. 호스트/포트/계정/네트워크 설정을 "
                f"확인하세요. (원인: {exc}){hint}"
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
