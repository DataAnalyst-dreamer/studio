# LGE.COM PLP 필터 그룹명 크롤러

제품 PLP 38개 각각의 필터 **그룹명**(그룹 내 개별 옵션값 제외)을 수집해
`plp_filter_groups.json` 으로 저장한다.

## 파일
- `lge_plp_group_crawler.py` — 크롤러 (전략 1: DOM 선택자 / 전략 2: `__NEXT_DATA__` JSON)
- `plp_filter_groups.json` — 결과(이어쓰기). 현재 **8/38** 채워짐(아래 참고).
- `manifest.json` — 38개 카테고리 목록 및 상태.
- `requirements.txt` — 의존성.

## 실행
```bash
pip install -r requirements.txt
python lge_plp_group_crawler.py
```
이미 채워진 카테고리는 건너뛰고, 비어 있는 것만 요청한다(요청 간 1초 지연).

## ⚠️ 네트워크 요건 (중요)
크롤러는 `www.lge.co.kr` 로 직접 HTTPS 요청을 보낸다.
**egress 정책이 lge.co.kr 을 허용하는 환경에서 실행해야 한다.**

Claude Code on the web 의 기본/제한 네트워크 정책 환경에서는 이 호스트가 차단되어
(프록시가 CONNECT 에 `403` 응답) 한 페이지도 받지 못한다. 이 경우:
1. 환경의 네트워크 정책을 `lge.co.kr` 접근이 가능한 정책으로 재설정한 뒤 **새 세션**을 시작하거나,
2. 로컬 PC(정상 인터넷)에서 위 명령으로 실행한다.

참고: https://code.claude.com/docs/en/claude-code-on-the-web

## 현재 채워진 8개 (manifest 의 `done`)
TV, 프로젝터, 노트북, 냉장고, 컨버터블 패키지, 김치냉장고, 세탁기, 의류건조기, 에어컨.

남은 30개는 네트워크가 열린 환경에서 크롤러를 재실행하면 채워진다.
선택자는 실제 HTML 구조를 확인해 최종 확정한다(현재 값은 후보 선택자 + `__NEXT_DATA__` 폴백).
