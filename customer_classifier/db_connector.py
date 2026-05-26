"""
Amazon Redshift 연결 모듈
- .env 파일에서 접속 정보를 읽어옵니다.
- 읽기 전용(SELECT) 쿼리만 허용합니다.
- 비밀번호는 로그·화면·오류 메시지에 절대 출력되지 않습니다.
"""

import os
from typing import Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

REQUIRED_KEYS = ["RS_HOST", "RS_PORT", "RS_DATABASE", "RS_USER", "RS_PASSWORD"]
FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "truncate",
    "alter", "create", "grant", "revoke",
]

_PSYCOPG2_AVAILABLE = False
_REDSHIFT_AVAILABLE = False

try:
    import psycopg2
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    pass

try:
    import redshift_connector
    _REDSHIFT_AVAILABLE = True
except ImportError:
    pass


def _mask_password(msg: str) -> str:
    """오류 메시지에서 비밀번호가 포함될 수 있는 부분을 마스킹"""
    password = os.getenv("RS_PASSWORD", "")
    if password and password in msg:
        msg = msg.replace(password, "****")
    return msg


def check_env() -> Tuple[bool, str]:
    """접속 정보가 모두 채워져 있는지 확인"""
    missing = [k for k in REQUIRED_KEYS if not os.getenv(k, "").strip()]
    if missing:
        return False, (
            f".env 파일에 다음 항목을 채워주세요: {', '.join(missing)}\n"
            ".env.example 파일을 복사해 .env 파일로 만든 뒤 값을 입력하세요."
        )
    return True, "접속 정보 확인 완료"


def _assert_select_only(sql: str) -> None:
    """SELECT 외 변경 쿼리 차단"""
    normalized = sql.strip().lower()
    for kw in FORBIDDEN_KEYWORDS:
        if normalized.startswith(kw) or f" {kw} " in normalized:
            raise ValueError(
                f"읽기 전용 모드입니다. '{kw.upper()}' 쿼리는 실행할 수 없습니다."
            )


def get_connection():
    """Redshift 연결 객체 반환 (psycopg2 우선, 없으면 redshift_connector 시도)"""
    ok, msg = check_env()
    if not ok:
        raise ConnectionError(msg)

    host = os.getenv("RS_HOST")
    port = int(os.getenv("RS_PORT", "5439"))
    database = os.getenv("RS_DATABASE")
    user = os.getenv("RS_USER")
    password = os.getenv("RS_PASSWORD")

    if _PSYCOPG2_AVAILABLE:
        try:
            conn = psycopg2.connect(
                host=host, port=port, dbname=database, user=user, password=password,
                connect_timeout=15,
            )
            return conn, "psycopg2"
        except Exception as e:
            raise ConnectionError(f"DB 연결 실패: {_mask_password(str(e))}")
    elif _REDSHIFT_AVAILABLE:
        try:
            conn = redshift_connector.connect(
                host=host, port=port, database=database, user=user, password=password,
            )
            return conn, "redshift_connector"
        except Exception as e:
            raise ConnectionError(f"DB 연결 실패: {_mask_password(str(e))}")
    else:
        raise ImportError(
            "DB 연결 라이브러리가 없습니다.\n"
            "터미널에서 다음 명령어를 실행하세요:\n"
            "  pip install psycopg2-binary redshift-connector"
        )


def test_connection() -> Tuple[bool, str]:
    try:
        conn, driver = get_connection()
        conn.close()
        return True, f"DB 연결 성공 (드라이버: {driver})"
    except Exception as e:
        return False, str(e)


def list_schemas(conn) -> list[str]:
    sql = """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_internal')
        ORDER BY schema_name
    """
    df = pd.read_sql(sql, conn)
    return df["schema_name"].tolist()


def list_tables(conn, schema: str) -> list[str]:
    sql = f"""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = '{schema}'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """
    df = pd.read_sql(sql, conn)
    return df["table_name"].tolist()


def list_columns(conn, schema: str, table: str) -> list[str]:
    sql = f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = '{schema}'
          AND table_name = '{table}'
        ORDER BY ordinal_position
    """
    df = pd.read_sql(sql, conn)
    return df["column_name"].tolist()


def fetch_data(
    conn,
    schema: str,
    table: str,
    col_text: str,
    col_date: Optional[str],
    col_product: Optional[str],
    col_id: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    limit: int = 10000,
) -> pd.DataFrame:
    select_cols = [f'"{col_text}"']
    if col_date:
        select_cols.append(f'"{col_date}"')
    if col_product:
        select_cols.append(f'"{col_product}"')
    if col_id:
        select_cols.append(f'"{col_id}"')

    where_clauses = []
    if col_date and date_from:
        where_clauses.append(f'"{col_date}" >= \'{date_from}\'')
    if col_date and date_to:
        where_clauses.append(f'"{col_date}" <= \'{date_to}\'')

    sql = f'SELECT {", ".join(select_cols)} FROM "{schema}"."{table}"'
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += f" LIMIT {limit}"

    _assert_select_only(sql)
    return pd.read_sql(sql, conn)


def execute_custom_sql(conn, sql: str, limit: int = 10000) -> pd.DataFrame:
    _assert_select_only(sql)
    # LIMIT가 없으면 자동 추가
    if "limit" not in sql.lower():
        sql = sql.rstrip(";") + f" LIMIT {limit}"
    return pd.read_sql(sql, conn)
