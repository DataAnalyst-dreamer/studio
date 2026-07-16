"""
개인정보(PII) 마스킹 모듈 — 외부 반출 전 민감정보 제거

Claude 등 외부 LLM에 집계 리포트를 올릴 때, 대표 인용문에 남아 있을 수 있는
고객 이름·연락처·주소·주문번호 등을 정규식 기반으로 가립니다.
LLM을 쓰지 않으므로 CPU만으로 즉시 동작합니다.

주의: 규칙 기반 마스킹은 100%를 보장하지 않습니다. 반출 전 사람이 한 번
훑어보는 것을 권장하며, 이 모듈은 "명백한 식별자"를 우선 제거하는 1차 방어선입니다.
"""

import re
from typing import Tuple

# ── 마스킹 규칙 (순서 중요: 넓은 패턴부터 좁은 패턴 순) ──────────────────

# 이메일
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# 휴대폰/전화 (010-1234-5678, 01012345678, 02-123-4567, +82 등)
_RE_PHONE = re.compile(
    r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"
)

# 카드번호 (4-4-4-4 또는 연속 16자리)
_RE_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){15}\d(?!\d)")

# 주민등록번호 (123456-1234567)
_RE_RRN = re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)")

# 계좌번호로 보이는 긴 숫자열 (하이픈 포함 10자리 이상)
_RE_ACCOUNT = re.compile(r"(?<!\d)\d{2,6}-\d{2,6}-\d{2,7}(?:-\d{1,7})?(?!\d)")

# 주문/문의/송장 번호 (영문접두 + 8자리 이상 숫자, 또는 순수 10자리 이상 숫자)
_RE_ORDER = re.compile(r"\b[A-Za-z]{1,4}\d{8,}\b")
_RE_LONGNUM = re.compile(r"(?<!\d)\d{10,}(?!\d)")

# 주소 (시/도 + 시/군/구 + 도로명/동 + 번지·상세 — 뒤 상세주소까지 최대한 흡수)
_RE_ADDRESS = re.compile(
    r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    r"(?:특별시|광역시|특별자치시|특별자치도|시|도)?\s*"
    r"(?:[가-힣]{1,10}(?:시|군|구)\s*){0,2}"
    r"[가-힣0-9]{1,15}(?:동|읍|면|리|로|길)"
    r"(?:\s*[0-9]{1,5}(?:-[0-9]{1,5})?(?:\s*번지|\s*번길)?)?"
    r"(?:\s*[0-9]{1,4}\s*(?:호|층|동|가))?"
    r"(?:\s*[가-힣0-9]{1,15}(?:아파트|빌라|타워|오피스텔|단지|파크))?"
)

# 이름 호칭 ("홍길동님", "김철수 고객님", "이OO님")
_RE_NAME_HONORIFIC = re.compile(
    r"[가-힣]{2,4}(?=\s?(?:님|고객님|회원님|씨|고객|회원)\b)"
)

# ── 치환 라벨 ───────────────────────────────────────────────────────────
_LABELS = {
    "email": "[이메일]",
    "phone": "[전화번호]",
    "card": "[카드번호]",
    "rrn": "[주민번호]",
    "account": "[계좌번호]",
    "order": "[주문번호]",
    "address": "[주소]",
    "name": "[이름]",
}


def mask_text(text: str) -> Tuple[str, int]:
    """
    한 문자열에서 PII를 마스킹.
    반환: (마스킹된 텍스트, 마스킹된 항목 수)
    """
    if not text:
        return text, 0

    count = 0

    def _sub(pattern: re.Pattern, label: str, s: str) -> str:
        nonlocal count
        n = len(pattern.findall(s))
        if n:
            count += n
            s = pattern.sub(label, s)
        return s

    # 넓은 식별자 → 좁은 식별자 순으로 처리 (긴 숫자열이 카드/주민번호를 덮지 않도록)
    text = _sub(_RE_EMAIL, _LABELS["email"], text)
    text = _sub(_RE_RRN, _LABELS["rrn"], text)
    text = _sub(_RE_CARD, _LABELS["card"], text)
    text = _sub(_RE_PHONE, _LABELS["phone"], text)
    text = _sub(_RE_ACCOUNT, _LABELS["account"], text)
    text = _sub(_RE_ORDER, _LABELS["order"], text)
    text = _sub(_RE_LONGNUM, _LABELS["order"], text)
    text = _sub(_RE_ADDRESS, _LABELS["address"], text)
    text = _sub(_RE_NAME_HONORIFIC, _LABELS["name"], text)

    return text, count


def mask_series(texts) -> Tuple[list, int]:
    """리스트/Series를 일괄 마스킹. 반환: (마스킹된 리스트, 총 마스킹 건수)"""
    masked = []
    total = 0
    for t in texts:
        m, n = mask_text(str(t) if t is not None else "")
        masked.append(m)
        total += n
    return masked, total
