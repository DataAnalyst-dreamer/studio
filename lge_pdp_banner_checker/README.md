# LGE.COM PDP 배너 노출 자동 점검 도구

Redshift에서 기간·카테고리 기준으로 SKU별 PDP URL을 조회하고, **Playwright 모바일
렌더링**으로 지정 배너 이미지(`mo-only`)의 실제 노출 여부를 자동 점검하는 내부 QA 도구입니다.

> 단순 HTML 문자열 검색이 아니라, 모바일 viewport에서 DOM 존재 → visible →
> `naturalWidth/Height > 0`(실제 로드)까지 검증하여 **PASS / WARN / FAIL / EXCLUDED**로 분류합니다.

## 주요 기능

- `.env` 기반 Redshift 접속 (named parameter `:start_date`, `:end_date`)
- 시작일/종료일 달력 선택 → 내부에서 `YYYYMMDD` 문자열로 변환
- 7개 컬럼 조회: `category, catg_lvl1_nm, catg_lvl2_nm, catg_lvl3_nm, sku, clean_page_url, vsit_pagenm`
- `category` 계층 기준 다중 선택(multiselect) 필터
- `/category/`, `/m/category/`, `/store/`, 비-LGE 도메인, 빈 URL → **EXCLUDED** 분류
- Playwright Chromium 모바일 viewport(390×844, isMobile) 렌더링 점검
- 개별 URL 오류가 전체 점검을 중단시키지 않음, 동시성 기본값 **3 이하**
- 결과를 CSV + HTML 리포트로 `outputs/`에 저장

## 기술 스택

Python 3.11+, Streamlit, pandas, python-dotenv, redshift-connector, Playwright, Jinja2, pytest

## 설치

```bash
cd lge_pdp_banner_checker
python -m venv .venv && source .venv/bin/activate   # 선택
pip install -r requirements.txt
playwright install chromium
```

## 환경 설정

`.env.example`을 복사해 `.env`를 만들고 Redshift 접속 정보를 채웁니다.
`.env`는 **절대 Git에 커밋하지 않습니다**(`.gitignore`에 포함됨). 읽기 전용 계정을 권장합니다.

```bash
cp .env.example .env
```

| 변수 | 설명 |
|------|------|
| `REDSHIFT_HOST/PORT/DATABASE/USER/PASSWORD` | 접속 정보 (필수) |
| `REDSHIFT_SSL` | SSL 사용 여부 (기본 true) |
| `REDSHIFT_SSLMODE` | `verify-ca`(기본) / `verify-full` |
| `REDSHIFT_CA_BUNDLE` | 사내 루트 CA 번들(.pem) 경로 (자가서명 체인 대응) |
| `REDSHIFT_SSL_INSECURE` | 인증서 검증 우회 (사내 QA 한정, 기본 false) |
| `DEFAULT_OUTPUT_DIR` | 리포트 저장 폴더 (기본 `outputs`) |
| `DEFAULT_CONCURRENCY` | 동시성 (1~3 강제) |
| `DEFAULT_TIMEOUT_MS` | URL당 timeout (기본 30000) |
| `BANNER_IMAGE_PATH` | 점검 대상 배너 경로 |

## 실행

```bash
streamlit run app.py
```

사용 흐름: **기간 선택 → 카테고리 후보 불러오기(Redshift) → 카테고리 계층 선택 →
점검 대상 미리보기 → 배너 점검 실행 → 결과 KPI/상세 확인 → CSV/HTML 다운로드**.

Redshift 접근이 어려운 환경에서는 사이드바에서 **샘플 파일 업로드** 또는 **데모 샘플**로
전처리·리포트 흐름을 점검할 수 있습니다.

## SSL 인증서 오류 대응

`Redshift 접속 실패 ... self-signed certificate in certificate chain` 오류는
대부분 **사내 보안장비의 TLS 가로채기(SSL inspection)** 때문입니다. 다음 순서로 해결하세요.

1. **(권장) 사내 루트 CA 신뢰 추가** — 보안팀에서 사내 루트 CA(.pem)를 받아 지정. 검증을 유지하므로 가장 안전합니다.
   ```bash
   REDSHIFT_CA_BUNDLE=/path/to/corp-root-ca.pem
   ```
2. **(사내 QA 한정) 검증 우회** — 암호화는 유지하되 서버 신원 검증을 생략합니다. 운영 환경 비권장.
   ```bash
   REDSHIFT_SSL_INSECURE=true
   ```
3. **평문 접속** — 클러스터가 비-SSL 접속을 허용하는 경우에만.
   ```bash
   REDSHIFT_SSL=false
   ```

> 참고: redshift_connector의 `ssl_insecure` 파라미터는 IAM IdP 인증서 전용이라
> user/password 인증에는 적용되지 않습니다. 본 도구는 `REDSHIFT_SSL_INSECURE=true`일 때
> DB 소켓 TLS 컨텍스트의 검증을 직접 비활성화합니다.

## 판정 기준

| 결과 | 정의 |
|------|------|
| `PASS` | 대상 이미지 DOM 존재 + visible + `naturalWidth/Height > 0` |
| `WARN` | DOM 존재하나 visible 아님 또는 로드 불완전 |
| `FAIL` | DOM에 이미지 없음 / 접근 실패·타임아웃 / 시스템 점검 페이지 |
| `EXCLUDED` | PDP가 아닌 URL(카테고리·스토어 등) 또는 제외 규칙 해당 |

## 프로젝트 구조

```
lge_pdp_banner_checker/
├── app.py                  # Streamlit UI 엔트리포인트
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── src/
│   ├── config.py           # .env 로드, 설정값 관리
│   ├── redshift_client.py  # Redshift 접속/쿼리 실행
│   ├── query_builder.py    # 날짜→YYYYMMDD, named parameter SQL
│   ├── data_preprocess.py  # URL 정제, PDP 판별, 중복 제거, 카테고리 필터
│   ├── banner_checker.py   # Playwright 모바일 배너 점검
│   ├── report_generator.py # CSV/HTML 리포트 생성
│   └── utils.py            # 샘플 데이터 로드 등
├── outputs/                # 리포트 저장 위치
└── tests/                  # pytest 단위 테스트
```

## 테스트

```bash
pytest -q
```

Playwright 브라우저 실행 없이 동작하는 순수 로직(쿼리 빌더, URL 전처리, 판정/집계,
리포트 생성)을 검증합니다.

## 비고 / 운영 주의

- 모바일 전용 배너이므로 PC viewport 점검만으로 PASS 처리하지 않습니다.
- 운영 사이트 부하/차단 방지를 위해 동시성은 3 이하로 제한됩니다.
- 시스템 점검/오류 페이지는 키워드로 감지해 `SITE_MAINTENANCE` 사유로 FAIL 처리합니다.
- 리포트에는 점검 조건, 요약 KPI, 카테고리별 집계, 상세 결과, FAIL/WARN 우선 목록이 포함됩니다.
