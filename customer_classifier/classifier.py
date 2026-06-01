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

CLASSIFICATION_PROMPT = """\
당신은 이커머스 고객 문의·리뷰를 분류하는 전문가입니다.
아래 [분류할 문장]을 읽고 반드시 아래 JSON 형식으로만 응답하세요.
JSON 외에 다른 텍스트(설명, 인사 등)는 절대 출력하지 마세요.

【실패수요】회사 실패·누락으로 발생한 불필요한 문의·불만
  세부분류(하나만 선택):
  배송지연 | 오배송/파손 | 결제/환불오류 | 상품정보불일치 | 설치/기사미흡 | CS응대불만 | AS처리지연 | 시스템오류 | 기타실패

【가치수요】구매·서비스 이용 의향이 있는 정상적이고 가치 있는 문의
  세부분류(하나만 선택):
  구매상담 | 스펙/호환성 | 가격/혜택 | 설치조건 | 사용방법 | AS사전문의 | 기타가치

【기타】분류 가치 없는 내용 (단순 칭찬, 별점만 있는 리뷰 등)
  세부분류: 해당없음

【판단보류】위 세 가지 중 어디에도 명확히 해당하지 않는 경우
  세부분류: 해당없음

출력 형식 (이것만 출력):
{"분류":"실패수요|가치수요|기타|판단보류", "세부분류":"위 세부분류 중 하나", "세부사유":"한 줄 요약", "근거":"판단 이유 한 문장", "확신도":숫자0~100}

출력 예시:
{"분류":"실패수요", "세부분류":"배송지연", "세부사유":"배송 지연으로 인한 현황 문의", "근거":"배송이 늦어진 이유를 묻는 전형적인 실패수요", "확신도":92}
{"분류":"가치수요", "세부분류":"구매상담", "세부사유":"에어컨 모델 비교 문의", "근거":"구매 전 모델을 비교하려는 가치 있는 문의", "확신도":88}

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
    "value": "가치수요", "value_demand": "가치수요", "가치": "가치수요",
    "other": "기타", "others": "기타",
    "pending": "판단보류", "uncertain": "판단보류", "undecided": "판단보류",
    "hold": "판단보류",
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


def _fallback_text_parse(text: str) -> Optional[dict]:
    """JSON 파싱 실패 시 텍스트에서 카테고리 키워드 직접 탐색"""
    for cat in ["실패수요", "가치수요", "기타", "판단보류"]:
        if cat in text:
            m = re.search(r'확신도[^\d]*(\d+)', text)
            confidence = int(m.group(1)) if m else 40
            # 세부분류도 텍스트에서 탐색
            subcat = _DEFAULT_SUBCAT.get(cat, "해당없음")
            valid_subs = VALID_SUBCATEGORIES.get(cat, set())
            for sub in valid_subs:
                if sub in text:
                    subcat = sub
                    break
            return {
                "분류":    cat,
                "세부분류": subcat,
                "세부사유": "텍스트 직접 파싱 (JSON 형식 아님)",
                "근거":    text[:150],
                "확신도":  min(confidence, 100),
            }
    return None


def _ollama_generate(model: str, prompt: str, timeout: int = 180) -> str:
    """
    스트리밍 방식으로 Ollama 텍스트 생성.
    stream=False는 일부 Ollama 버전에서 HTTP 500을 유발하므로 스트리밍 사용.
    """
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": True},
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


def classify_one(text: str, model: str, retries: int = 3) -> dict:
    """문의 1건 분류. 스트리밍 방식으로 Ollama 호출."""
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
                        return fallback
                    category = "판단보류"
                    parsed["세부사유"] = str(parsed.get("세부사유", "")) + " [카테고리 수정됨]"
                    parsed["세부분류"] = "해당없음"

                try:
                    confidence = max(0, min(100, int(parsed.get("확신도", 50))))
                except (ValueError, TypeError):
                    confidence = 50

                return {
                    "분류":    category,
                    "세부분류": str(parsed.get("세부분류", _DEFAULT_SUBCAT.get(category, "해당없음")))[:50],
                    "세부사유": str(parsed.get("세부사유", ""))[:200],
                    "근거":    str(parsed.get("근거", ""))[:300],
                    "확신도":  confidence,
                }

            # 2차: 텍스트 직접 탐색 (fallback)
            fallback = _fallback_text_parse(raw)
            if fallback:
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
    }


def classify_batch(
    texts: list[str],
    model: str,
    progress_callback=None,
    stop_flag: Optional[list] = None,
    checkpoint_callback=None,
    checkpoint_interval: int = 50,
) -> list[dict]:
    results = []
    total   = len(texts)

    for i, text in enumerate(texts):
        if stop_flag and stop_flag[0]:
            break

        result = classify_one(text, model)
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, total)

        if checkpoint_callback and (i + 1) % checkpoint_interval == 0:
            checkpoint_callback(results)

    return results
