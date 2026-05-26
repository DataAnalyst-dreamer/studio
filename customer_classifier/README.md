# 고객 문의·리뷰 자동 분류 프로그램

LGE.COM CS 전략 과제 — Ollama 로컬 LLM + Amazon Redshift

## 빠른 시작

```bash
# 1. 라이브러리 설치
pip install -r requirements.txt

# 2. (DB 사용 시) 접속 정보 설정
cp .env.example .env
# .env 파일을 열어 실제 값 입력

# 3. Ollama 실행 및 모델 다운로드 (별도 터미널)
ollama serve
ollama pull exaone3.5

# 4. 프로그램 실행
streamlit run app.py
```

## 파일 구조

```
customer_classifier/
├── app.py              # 메인 Streamlit 앱
├── classifier.py       # Ollama LLM 분류 엔진
├── data_loader.py      # 파일·DB 데이터 로딩
├── db_connector.py     # Redshift 연결 모듈
├── utils.py            # 공통 유틸리티
├── requirements.txt    # 필요 라이브러리
├── .env.example        # 접속 정보 템플릿
└── .gitignore
```

자세한 사용법은 프로그램 실행 후 **도움말** 탭을 참고하세요.
