"""
분류 엔진 — Ollama 로컬 LLM 호출 및 결과 파싱
"""

import json
import re
import time
from typing import Optional

import requests

from utils import safe_json_parse

OLLAMA_BASE_URL = "http://localhost:11434"

# ── 약한 PC / 소형 모델 대응 생성 옵션 ──────────────────────────────────
# temperature=0  : 분류는 창의성이 필요 없으므로 결정적 출력 → 일관성·재현성 향상
# num_predict     : 출력은 JSON 한 줄이면 충분 → 길이 제한으로 속도 대폭 향상
# top_p/top_k     : 후보를 좁혀 헛소리·형식 이탈 감소
# keep_alive      : 모델을 메모리에 상주시켜 건별 재로딩 오버헤드 제거 (연속 분류 시 핵심)
GEN_OPTIONS = {
    "temperature": 0,
    "num_predict": 256,
    "top_p": 0.9,
    "top_k": 20,
    "repeat_penalty": 1.1,
}
KEEP_ALIVE = "10m"

CLASSIFICATION_PROMPT = """\
당신은 LG전자 온라인몰(LGE.COM)의 고객 문의를 분류하는 CS 전략 분석 전문가입니다.
아래 [분류할 문장]을 읽고, 반드시 마지막의 JSON 형식으로만 답하세요.

═══════════ 핵심 개념 ═══════════
■ 가치수요 = 회사가 "원하는" 좋은 수요.
  구매를 검토·진행하거나, 정상적으로 제품을 쓰려는 고객의 자연스러운 질문.
  회사가 잘 대응하면 매출·만족으로 이어진다.
  (구매 전 정보 탐색, 호환성·스펙 확인, 가격·혜택 확인, 설치 조건, 사용법 등)

■ 실패수요 = 회사의 "실패"로 생긴 불필요한 수요.
  무언가 잘못됐거나 빠졌기 때문에 고객이 어쩔 수 없이 하는 문의·불만.
  회사가 일을 제대로 했다면 애초에 생기지 않았을 문의다.
  (배송 지연, 결제·시스템 오류, 정보 불일치, 제품 고장·AS, 응대 불만 등)

★ 판단 공식 (반드시 적용):
  "회사가 일을 완벽히 했어도 고객이 이 질문을 했을까?"
   → 예 (사고 싶거나 쓰려고 자연스럽게 묻는 것)         = 가치수요
   → 아니오 (문제·오류·누락 때문에 어쩔 수 없이 묻는 것) = 실패수요

═══════════ 중요 규칙 ═══════════
① 판단보류는 거의 쓰지 마세요. 의미 없는 빈 글·욕설·도저히 알 수 없는 횡설수설일 때만.
   질문 내용이 조금이라도 파악되면 반드시 가치수요 또는 실패수요로 결정하세요.
② "호환되나요 / 스펙 / 사이즈 / 재입고 / 할인 맞나요 / 설치 가능한가요 / 사용법" → 대부분 가치수요.
③ "배송 늦어요 / 결제·예약 안돼요 / 고장났어요 / 정보가 다르게 적혀있어요 / 답변이 이상해요" → 실패수요.

═══════════ 세부분류 ═══════════
[가치수요] 중 하나 선택:
  구매상담   : 모델 추천·구매 의향·재입고/구매 가능 여부
  스펙/호환성: 호환 여부, 스펙·치수·전자파·케이블규격 등 제품 사양 확인
  가격/혜택  : 할인·쿠폰·포인트·멤버십·캐시백 확인
  설치조건   : 설치 가능 여부·조건·비용, 기사 설치 범위, 직접 설치 가능 여부
  사용방법   : 사용법·설정·기능 동작 방식 문의
  AS사전문의 : 보증기간·AS 절차·부품 구매 방법 (아직 고장 전 단계)
  기타가치   : 색상 옵션·구성품 등 그 외 구매/사용 관련

[실패수요] 중 하나 선택:
  배송지연      : 배송이 늦음·배송일이 이상함·언제 오는지 답답함
  오배송/파손   : 다른 물건이 옴·받아보니 파손/불량
  결제/환불오류 : 결제 실패·중복결제·환불 지연
  상품정보불일치: 페이지의 설명·사진·출시연도·가격 정보가 틀리거나 서로 다름
  설치/기사미흡 : 기사 미방문·설치 불량·설치 약속 어긋남
  CS응대불만    : 상담 답변이 틀림·서로 다름·불친절·답변 없음
  AS처리지연    : 제품이 고장나서 수리/AS 필요 (이미 문제 발생)
  시스템오류    : 주문·예약·등록·앱·웹이 오류로 안 됨 (예약날짜 안뜸, 시리얼 등록 불가, 글자수 제한)
  기타실패      : 그 외 회사 실패로 인한 문의

[기타] 세부분류: 해당없음   (단순 칭찬·별점만 있는 리뷰)
[판단보류] 세부분류: 해당없음

═══════════ 예시 ═══════════
"OLED77C2FNA와 호환되나요?" →
{"분류":"가치수요","세부분류":"스펙/호환성","세부사유":"보유 TV와 호환 여부 확인","근거":"구매 검토를 위한 자연스러운 호환성 질문이므로 가치수요","확신도":92}
"재입고 일정 있나요? 구매하려다 못했어요" →
{"분류":"가치수요","세부분류":"구매상담","세부사유":"품절 상품 재입고 일정 문의","근거":"사려는 의향이 분명한 구매 문의이므로 가치수요","확신도":90}
"55% 할인 맞나요?" →
{"분류":"가치수요","세부분류":"가격/혜택","세부사유":"표시 할인율 확인","근거":"구매 전 가격 확인은 정상적인 가치수요","확신도":88}
"기사님이 전기공사도 해주시나요?" →
{"분류":"가치수요","세부분류":"설치조건","세부사유":"설치 기사 작업 범위 확인","근거":"설치 가능 여부를 미리 확인하는 가치수요","확신도":85}
"4월1일 결제했는데 배송이 너무 늦어요" →
{"분류":"실패수요","세부분류":"배송지연","세부사유":"결제 후 배송 지연 불만","근거":"제때 배송됐다면 없었을 문의이므로 실패수요","확신도":95}
"예약날짜가 안떠서 구매를 못해요" →
{"분류":"실패수요","세부분류":"시스템오류","세부사유":"예약일 선택 불가로 주문 불가","근거":"주문 시스템 오류로 발생한 실패수요","확신도":93}
"리모콘이 갑자기 고장났어요. 다시 사야 하나요?" →
{"분류":"실패수요","세부분류":"AS처리지연","세부사유":"리모콘 고장 AS/교체 문의","근거":"제품 고장으로 어쩔 수 없이 생긴 실패수요","확신도":90}
"출시연도가 어디는 2024, 어디는 2026으로 적혀있어요" →
{"분류":"실패수요","세부분류":"상품정보불일치","세부사유":"상품 페이지 출시연도 정보 불일치","근거":"정보가 정확했다면 없었을 문의이므로 실패수요","확신도":90}

═══════════ 출력 형식 (이 JSON 한 줄만 출력) ═══════════
{"분류":"가치수요 또는 실패수요 또는 기타 또는 판단보류","세부분류":"위 목록 중 하나","세부사유":"무엇을 묻는지 한 줄 요약","근거":"왜 그 분류인지(특히 실패/가치 판단 이유) 한 문장","확신도":숫자0~100}

[분류할 문장]:
"""

VALID_CATEGORIES = {"실패수요", "가치수요", "기타", "판단보류"}

VALID_SUBCATEGORIES: dict[str, set] = {
    "실패수요": {"배송지연", "오배송/파손", "결제/환불오류", "상품정보불일치",
                "설치/기사미흡", "CS응대불만", "AS처리지연", "시스템오류", "기타실패"},
    "가치수요": {"구매상담", "스펙/호환성", "가격/혜택", "설치조건",
                "사용방법", "AS사전문의", "기타가치"},
    "기타":    {"해당없음"},
    "판단보류": {"해당없음"},
}

_DEFAULT_SUBCAT = {
    "실패수요": "기타실패",
    "가치수요": "기타가치",
    "기타":    "해당없음",
    "판단보류": "해당없음",
}

_KEY_MAP = {
    "category": "분류", "class": "분류", "classification": "분류",
    "type": "분류", "label": "분류",
    "sub_category": "세부분류", "subcategory": "세부분류", "subclass": "세부분류",
    "sub_type": "세부분류", "subtype": "세부분류", "detail_type": "세부분류",
    "reason": "세부사유", "detail": "세부사유", "summary": "세부사유",
    "basis": "근거", "evidence": "근거", "explanation": "근거",
    "confidence": "확신도", "score": "확신도", "certainty": "확신도",
}

_CAT_MAP = {
    "failure": "실패수요", "failure_demand": "실패수요", "실패": "실패수요",
    "실패수용": "실패수요",
    "value": "가치수요", "value_demand": "가치수요", "가치": "가치수요",
    "가치수용": "가치수요",
    "other": "기타", "others": "기타",
    "pending": "판단보류", "uncertain": "판단보류", "undecided": "판단보류",
    "hold": "판단보류", "판정보류": "판단보류", "보류": "판단보류",
}


def _normalize_parsed(parsed: dict) -> dict:
    result = {}
    for k, v in parsed.items():
        result[_KEY_MAP.get(k.lower(), k)] = v
    cat = str(result.get("분류", "")).strip()
    result["분류"] = _CAT_MAP.get(cat.lower(), cat)
    # 세부분류 검증 및 기본값 설정
    subcat = str(result.get("세부분류", "")).strip()
    valid_subs = VALID_SUBCATEGORIES.get(result["분류"], set())
    if subcat not in valid_subs:
        result["세부분류"] = _DEFAULT_SUBCAT.get(result["분류"], "해당없음")
    return result


def _field_regex(text: str, *keys: str) -> Optional[str]:
    """깨진 JSON·일반 텍스트에서 "키":"값" 형태의 값을 정규식으로 추출"""
    for key in keys:
        # "키":"값"  또는  키:값  (따옴표 유무·공백 허용)
        m = re.search(rf'"?{key}"?\s*[:：]\s*"([^"\n]*)"', text)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m = re.search(rf'"?{key}"?\s*[:：]\s*([^",}}\n]+)', text)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def _fallback_text_parse(text: str) -> Optional[dict]:
    """
    JSON 파싱 실패 시, 깨진 JSON에서도 각 필드를 정규식으로 직접 추출.
    (예: '...근거":"..."}, "확신도":85}' 같은 구조 오류도 값 복원)
    raw 텍스트를 그대로 근거에 넣지 않고, 가능한 한 실제 값을 복원한다.
    """
    # 1) 분류 결정: 명시된 분류값 우선, 없으면 본문에서 키워드 탐색
    cat_raw = _field_regex(text, "분류", "category", "class")
    cat = None
    if cat_raw:
        cat = _CAT_MAP.get(cat_raw.lower(), cat_raw)
    if cat not in VALID_CATEGORIES:
        cat = None
        for c in ["실패수요", "가치수요", "기타", "판단보류"]:
            if c in text or _CAT_MAP.get(c, "") == c and c in text:
                cat = c
                break
        # 오타 대응
        if cat is None:
            for typo, real in [("판정보류", "판단보류"), ("실패수용", "실패수요"), ("가치수용", "가치수요")]:
                if typo in text:
                    cat = real
                    break
    if cat is None:
        return None

    # 2) 세부분류: 명시값 검증 → 없으면 본문에서 유효 세부분류 탐색 → 기본값
    valid_subs = VALID_SUBCATEGORIES.get(cat, set())
    subcat_raw = _field_regex(text, "세부분류", "subcategory", "sub_category")
    subcat = subcat_raw if subcat_raw in valid_subs else None
    if subcat is None:
        for sub in valid_subs:
            if sub in text:
                subcat = sub
                break
    if subcat is None:
        subcat = _DEFAULT_SUBCAT.get(cat, "해당없음")

    # 3) 세부사유·근거·확신도 복원
    reason = _field_regex(text, "세부사유", "reason", "summary") or ""
    basis  = _field_regex(text, "근거", "basis", "evidence") or ""
    conf_m = re.search(r'"?확신도"?\s*[:：]\s*"?(\d+)', text)
    confidence = int(conf_m.group(1)) if conf_m else 50

    # 복원 실패 시 너무 긴 raw 덤프는 피하고 짧게만
    if not reason:
        reason = "형식 오류 응답에서 복원"
    if not basis:
        basis = text.strip()[:120]

    return {
        "분류":    cat,
        "세부분류": subcat,
        "세부사유": reason[:200],
        "근거":    basis[:300],
        "확신도":  max(0, min(confidence, 100)),
    }


def _ollama_generate(
    model: str,
    prompt: str,
    timeout: int = 180,
    force_json: bool = True,
) -> str:
    """
    스트리밍 방식으로 Ollama 텍스트 생성.
    stream=False는 일부 Ollama 버전에서 HTTP 500을 유발하므로 스트리밍 사용.

    force_json=True 이면 Ollama의 구조화 출력(format="json")을 사용해
    소형 모델에서도 유효한 JSON이 나오도록 강제한다 → 파싱 실패율 감소.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": GEN_OPTIONS,
        "keep_alive": KEEP_ALIVE,
    }
    if force_json:
        payload["format"] = "json"

    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        stream=True,
        timeout=timeout,
    )

    if resp.status_code != 200:
        try:
            err_body = resp.json()
            err_msg = err_body.get("error", f"HTTP {resp.status_code}")
        except Exception:
            err_msg = f"HTTP {resp.status_code}"

        if resp.status_code == 500:
            err_lower = err_msg.lower()
            is_ram = any(k in err_lower for k in ["allocate", "buffer", "memory", "terminated", "panic"])
            if is_ram:
                raise requests.HTTPError(
                    f"HTTP 500 — RAM 부족으로 모델을 실행할 수 없습니다. "
                    f"'ollama pull qwen2.5:3b' 으로 더 작은 모델을 설치한 뒤 사이드바에서 변경하세요. "
                    f"(exaone3.5는 RAM 10GB 이상 필요, qwen2.5:3b는 4GB로 동작)\n"
                    f"Ollama 오류: {err_msg}"
                )
            raise requests.HTTPError(
                f"HTTP 500 — 모델 실행 실패. "
                f"터미널에서 'ollama run {model}' 을 직접 실행해 모델이 정상 동작하는지 확인하세요. "
                f"동작하지 않으면 'ollama pull {model}' 로 재설치하거나 더 작은 모델을 선택하세요.\n"
                f"Ollama 오류: {err_msg}"
            )
        raise requests.HTTPError(err_msg)

    full_response = ""
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            chunk = json.loads(line)
            if "error" in chunk:
                raise requests.HTTPError(chunk["error"])
            full_response += chunk.get("response", "")
            if chunk.get("done", False):
                break
        except json.JSONDecodeError:
            continue

    return full_response


def check_ollama() -> tuple[bool, str]:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            return True, "Ollama 실행 중"
        return False, f"Ollama 응답 오류 (상태 코드: {resp.status_code})"
    except requests.exceptions.ConnectionError:
        return False, (
            "Ollama가 실행되지 않았습니다.\n"
            "터미널에서 'ollama serve' 명령어를 실행한 뒤 새로고침하세요."
        )
    except Exception as e:
        return False, f"Ollama 연결 오류: {e}"


def list_models() -> list[str]:
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def diagnose_one(text: str, model: str) -> dict:
    """진단용 — raw 응답과 파싱 과정을 모두 반환"""
    prompt = CLASSIFICATION_PROMPT + text.strip()
    try:
        raw_text = _ollama_generate(model, prompt)
        parsed   = safe_json_parse(raw_text)
        if parsed:
            parsed = _normalize_parsed(parsed)
        fallback = _fallback_text_parse(raw_text) if not parsed else None
        final    = classify_one(text, model)
        return {
            "http_status":    200,
            "ollama_error":   "",
            "raw_response":   raw_text[:1000],
            "parsed_json":    parsed,
            "fallback_parse": fallback,
            "final_result":   final,
        }
    except requests.HTTPError as e:
        return {"http_status": None, "ollama_error": str(e), "raw_response": "", "parsed_json": None, "fallback_parse": None, "final_result": None}
    except requests.exceptions.Timeout:
        return {"http_status": None, "ollama_error": "타임아웃 (180초 초과) — 더 작은 모델 사용 권장", "raw_response": "", "parsed_json": None, "fallback_parse": None, "final_result": None}
    except Exception as e:
        return {"http_status": None, "ollama_error": str(e), "raw_response": "", "parsed_json": None, "fallback_parse": None, "final_result": None}


# ══════════════════════════════════════════════════════════════════════
# 규칙 기반 고속 사전분류 (LLM 호출 전 명백한 건을 먼저 처리)
# ──────────────────────────────────────────────────────────────────────
# 약한 PC에서 LLM 물량 자체를 줄이기 위한 장치.
# ★ 오분류를 막기 위해 "거의 확실한" 패턴만 등록한다. 조금이라도 애매하면
#   규칙에 넣지 말고 LLM으로 넘긴다. (예: '재입고'는 가치수요지만 문맥에 따라
#   실패로 오해될 수 있어 규칙에서 제외)
# 각 규칙: (분류, 세부분류, 반드시_포함(list, 각 항목 중 하나라도), 확신도, 사유)
#   required 는 [group1, group2, ...] 형태로, 모든 group에서 최소 한 단어가
#   본문에 나타나야 매칭된다 (AND of ORs).
# ══════════════════════════════════════════════════════════════════════

_RULES: list[tuple] = [
    # ── 실패수요 ──────────────────────────────────────────────
    ("실패수요", "배송지연",
     [["배송", "택배", "발송", "출고"], ["늦", "언제 와", "언제와", "안 와", "안와",
      "며칠째", "아직도", "지연", "안 옵니", "안옵니", "감감"]], 82,
     "배송 지연 관련 표현 — 규칙 매칭"),
    ("실패수요", "결제/환불오류",
     [["환불", "결제", "취소"], ["안 되", "안돼", "안됩", "실패", "오류", "중복",
      "지연", "언제 되", "안 해", "누락"]], 82,
     "결제·환불 오류 표현 — 규칙 매칭"),
    ("실패수요", "시스템오류",
     [["앱", "사이트", "홈페이지", "웹", "예약", "등록", "로그인", "주문"],
      ["오류", "에러", "안 떠", "안떠", "안 뜨", "안뜨", "먹통", "안 되", "안돼",
       "튕겨", "멈춰", "버벅"]], 80,
     "시스템 오류 표현 — 규칙 매칭"),
    ("실패수요", "오배송/파손",
     [["파손", "깨져", "깨진", "불량", "오배송", "다른 제품", "다른 상품",
       "찌그러", "흠집"]], 84,
     "오배송·파손 표현 — 규칙 매칭"),
    # ── 가치수요 ──────────────────────────────────────────────
    ("가치수요", "스펙/호환성",
     [["호환"], ["되나", "가능", "맞나", "여부", "?", "될까", "인가요"]], 82,
     "호환성 확인 문의 — 규칙 매칭"),
]


def rule_classify(text: str) -> Optional[dict]:
    """
    본문을 규칙으로 사전 분류. 매칭되면 결과 dict, 아니면 None.
    매우 보수적으로 매칭하며, 결과에는 출처='규칙' 을 표기해 검토 시 구분 가능.
    """
    t = text.strip()
    if len(t) < 4:
        return None
    low = t.lower()

    for cat, subcat, groups, conf, reason in _RULES:
        if all(any(w.lower() in low for w in group) for group in groups):
            return {
                "분류":    cat,
                "세부분류": subcat,
                "세부사유": (t[:60] + "…") if len(t) > 60 else t,
                "근거":    reason,
                "확신도":  conf,
                "출처":    "규칙",
            }
    return None


def classify_one(text: str, model: str, retries: int = 3, use_rules: bool = True) -> dict:
    """문의 1건 분류. 규칙 우선 → 미매칭 시 Ollama LLM 호출."""
    if use_rules:
        ruled = rule_classify(text)
        if ruled is not None:
            return ruled

    prompt = CLASSIFICATION_PROMPT + text.strip()

    last_error = ""
    for attempt in range(retries):
        try:
            raw = _ollama_generate(model, prompt)

            if not raw.strip():
                last_error = "응답이 비어 있음 — 모델 로딩 중이거나 메모리 부족"
                if attempt < retries - 1:
                    time.sleep(3)
                continue

            # 1차: JSON 파싱
            parsed = safe_json_parse(raw)
            if parsed:
                parsed   = _normalize_parsed(parsed)
                category = parsed.get("분류", "")
                if category not in VALID_CATEGORIES:
                    fallback = _fallback_text_parse(raw)
                    if fallback:
                        fallback["출처"] = "LLM(복원)"
                        return fallback
                    category = "판단보류"
                    parsed["세부사유"] = str(parsed.get("세부사유", "")) + " [카테고리 수정됨]"
                    parsed["세부분류"] = "해당없음"

                # 확신도: 파싱값 우선, 없으면(깨진 JSON 등) 원본에서 보충
                confidence = None
                if "확신도" in parsed:
                    try:
                        confidence = max(0, min(100, int(parsed.get("확신도"))))
                    except (ValueError, TypeError):
                        confidence = None
                if confidence is None:
                    conf_m = re.search(r'"?확신도"?\s*[:：]\s*"?(\d+)', raw)
                    confidence = max(0, min(100, int(conf_m.group(1)))) if conf_m else 50

                # 세부분류 검증 (대분류와 짝이 맞지 않으면 기본값)
                subcat = str(parsed.get("세부분류", "")).strip()
                if subcat not in VALID_SUBCATEGORIES.get(category, set()):
                    subcat = _DEFAULT_SUBCAT.get(category, "해당없음")

                return {
                    "분류":    category,
                    "세부분류": subcat[:50],
                    "세부사유": str(parsed.get("세부사유", ""))[:200],
                    "근거":    str(parsed.get("근거", ""))[:300],
                    "확신도":  confidence,
                    "출처":    "LLM",
                }

            # 2차: 텍스트 직접 탐색 (fallback)
            fallback = _fallback_text_parse(raw)
            if fallback:
                fallback["출처"] = "LLM(복원)"
                return fallback

            last_error = f"JSON 파싱 실패 (응답: {raw[:120]})"

        except requests.HTTPError as e:
            last_error = str(e)[:300]
            # HTTP 500은 재시도해도 해결 안 됨 → 즉시 반환
            if "HTTP 500" in last_error:
                break
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.Timeout:
            last_error = "타임아웃 (180초 초과) — 더 작은 모델 사용 권장"
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            last_error = str(e)[:200]
            if attempt < retries - 1:
                time.sleep(2 ** attempt)

    return {
        "분류":    "분류실패",
        "세부분류": "해당없음",
        "세부사유": last_error[:200],
        "근거":    "재시도 후에도 유효한 응답을 받지 못했습니다.",
        "확신도":  0,
        "출처":    "실패",
    }


def classify_batch(
    texts: list[str],
    model: str,
    progress_callback=None,
    stop_flag: Optional[list] = None,
    checkpoint_callback=None,
    checkpoint_interval: int = 50,
    use_rules: bool = True,
) -> list[dict]:
    results = []
    total   = len(texts)

    for i, text in enumerate(texts):
        if stop_flag and stop_flag[0]:
            break

        result = classify_one(text, model, use_rules=use_rules)
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, total)

        if checkpoint_callback and (i + 1) % checkpoint_interval == 0:
            checkpoint_callback(results)

    return results
