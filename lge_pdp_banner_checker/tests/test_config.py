"""config 모듈 SSL 옵션 파싱 테스트."""

import importlib

from src import config as config_module


def _reload_with_env(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(config_module)
    return config_module.load_config()


def test_ssl_defaults(monkeypatch):
    for k in ("REDSHIFT_SSL", "REDSHIFT_SSLMODE", "REDSHIFT_CA_BUNDLE",
              "REDSHIFT_SSL_INSECURE"):
        monkeypatch.delenv(k, raising=False)
    cfg = config_module.load_config()
    assert cfg.redshift.ssl is True
    assert cfg.redshift.sslmode == "verify-ca"
    assert cfg.redshift.ca_bundle is None
    assert cfg.redshift.ssl_insecure is False


def test_ssl_insecure_and_mode(monkeypatch):
    cfg = _reload_with_env(
        monkeypatch,
        REDSHIFT_SSL="true",
        REDSHIFT_SSLMODE="verify-full",
        REDSHIFT_SSL_INSECURE="true",
        REDSHIFT_CA_BUNDLE="/tmp/corp-ca.pem",
    )
    assert cfg.redshift.sslmode == "verify-full"
    assert cfg.redshift.ssl_insecure is True
    assert cfg.redshift.ca_bundle == "/tmp/corp-ca.pem"


def test_ssl_disabled(monkeypatch):
    cfg = _reload_with_env(monkeypatch, REDSHIFT_SSL="false")
    assert cfg.redshift.ssl is False


def test_concurrency_capped(monkeypatch):
    cfg = _reload_with_env(monkeypatch, DEFAULT_CONCURRENCY="10")
    assert cfg.concurrency == 3


def test_insecure_ssl_context_disables_verification():
    from src.redshift_client import _insecure_ssl_patch
    import ssl

    with _insecure_ssl_patch():
        from ssl import CERT_REQUIRED, SSLContext, PROTOCOL_TLS_CLIENT

        # 1) bare SSLContext()에 검증을 켜려 해도 무시된다
        bare = SSLContext()
        bare.verify_mode = CERT_REQUIRED
        bare.check_hostname = True
        assert bare.verify_mode == ssl.CERT_NONE
        assert bare.check_hostname is False

        # 2) PROTOCOL_TLS_CLIENT로 생성돼 C 레벨에서 검증이 켜진 경우도 꺼진다
        client = SSLContext(PROTOCOL_TLS_CLIENT)
        assert client.verify_mode == ssl.CERT_NONE
        assert client.check_hostname is False

        # 3) create_default_context도 패치된 전역 SSLContext를 사용해 비활성화된다
        default = ssl.create_default_context()
        assert default.verify_mode == ssl.CERT_NONE
        assert default.check_hostname is False

    # 패치 해제 후 원복 확인
    assert ssl.create_default_context().verify_mode == ssl.CERT_REQUIRED
