"""환경설정 로드 모듈.

`.env` 파일에서 Redshift 접속 정보와 점검 도구 기본값을 읽어
구조화된 설정 객체로 제공한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 기본 배너 경로 (PRD 9.1)
DEFAULT_BANNER_IMAGE_PATH = "/kr/home-main-pdp/2026/JUN/pdp_banner_656x220.png"

# 모바일 viewport 기본값 (PRD 8.6 / FR-006)
DEFAULT_VIEWPORT = {"width": 390, "height": 844}
DEFAULT_DEVICE_SCALE_FACTOR = 3
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)


def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: Optional[str], default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RedshiftConfig:
    """Redshift 접속 설정."""

    host: str
    port: int
    database: str
    user: str
    password: str
    ssl: bool = True
    # 'verify-ca'(기본) 또는 'verify-full'. redshift_connector가 지원하는 값.
    sslmode: str = "verify-ca"
    # 사내 루트 CA 번들(.pem) 경로. 지정 시 신뢰 저장소에 추가된다.
    ca_bundle: Optional[str] = None
    # 사내 QA 환경에서 자가서명 인증서 체인 검증을 우회할 때 True.
    # (운영 환경 비권장) 검증 없이 암호화만 수행한다.
    ssl_insecure: bool = False

    def is_complete(self) -> bool:
        """필수 접속 정보가 모두 채워졌는지 확인한다."""
        return all([self.host, self.database, self.user, self.password])

    def missing_fields(self) -> list[str]:
        """비어 있는 필수 항목 목록을 반환한다."""
        missing = []
        for name in ("host", "database", "user", "password"):
            if not getattr(self, name):
                missing.append(f"REDSHIFT_{name.upper()}")
        return missing


@dataclass(frozen=True)
class AppConfig:
    """애플리케이션 전체 설정."""

    redshift: RedshiftConfig
    output_dir: str = "outputs"
    concurrency: int = 3
    timeout_ms: int = 30000
    banner_image_path: str = DEFAULT_BANNER_IMAGE_PATH
    viewport: dict = field(default_factory=lambda: dict(DEFAULT_VIEWPORT))
    device_scale_factor: int = DEFAULT_DEVICE_SCALE_FACTOR
    user_agent: str = DEFAULT_USER_AGENT

    def output_path(self) -> Path:
        path = Path(self.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


def load_config(dotenv_path: Optional[str] = None) -> AppConfig:
    """`.env`(있으면)를 로드하고 AppConfig를 구성한다.

    동시성은 부하 방지를 위해 1~3 사이로 강제한다(PRD 12 / 비기능 요구사항).
    """
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)
    else:
        load_dotenv(override=False)

    ca_bundle = os.getenv("REDSHIFT_CA_BUNDLE", "").strip() or None
    redshift = RedshiftConfig(
        host=os.getenv("REDSHIFT_HOST", "").strip(),
        port=_to_int(os.getenv("REDSHIFT_PORT"), 5439),
        database=os.getenv("REDSHIFT_DATABASE", "").strip(),
        user=os.getenv("REDSHIFT_USER", "").strip(),
        password=os.getenv("REDSHIFT_PASSWORD", ""),
        ssl=_to_bool(os.getenv("REDSHIFT_SSL"), default=True),
        sslmode=(os.getenv("REDSHIFT_SSLMODE", "").strip() or "verify-ca"),
        ca_bundle=ca_bundle,
        ssl_insecure=_to_bool(os.getenv("REDSHIFT_SSL_INSECURE"), default=False),
    )

    concurrency = _to_int(os.getenv("DEFAULT_CONCURRENCY"), 3)
    # 동시성 상한 강제: 사이트 부하/차단 방지
    concurrency = max(1, min(concurrency, 3))

    return AppConfig(
        redshift=redshift,
        output_dir=os.getenv("DEFAULT_OUTPUT_DIR", "outputs").strip() or "outputs",
        concurrency=concurrency,
        timeout_ms=_to_int(os.getenv("DEFAULT_TIMEOUT_MS"), 30000),
        banner_image_path=os.getenv(
            "BANNER_IMAGE_PATH", DEFAULT_BANNER_IMAGE_PATH
        ).strip()
        or DEFAULT_BANNER_IMAGE_PATH,
    )
