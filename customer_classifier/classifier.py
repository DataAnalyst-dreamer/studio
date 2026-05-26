"""
분류 엔진 — Ollama 로컬 LLM 호출 및 결과 파싱
"""

import json
import time
from typing import Optional

import requests

from utils import safe_json_parse

OLLAMA_BASE_URL = "http://localhost:11434"

CLASSIFICATION_PROMPT = """당신은 이커머스 고객 문의/리뷰를 분류하는 전문가입니다.
아래 문장을 읽고 다음 중 하나로 분류하세요.

[실패수요] = 회사의 실패/누락 때문에 생긴, 없었어도 될 문의·불만:
 예) "배송이 일주일째 안 와요" / "결제했는데 주문이 안 됐어요" / "상품이 설명과 달라요"
     "취소 요청했는데 처리가 안 됐어요" / "설치 기사가 약속시간에 안 왔어요" / "또 같은 문제로 연락해요"

[가치수요] = 구매하려는 고객의 정상적이고 가치 있는 문의:
 예) "이 모델이랑 저 모델 중 뭐가 좋아요?" / "우리 집 주방에 맞을까요?"
     "두 개 같이 사면 할인되나요?" / "구독이 나아요 일시불이 나아요?" / "설치 조건이 어떻게 되나요?"

규칙:
- 단순 칭찬/별점만 있는 리뷰는 [기타]로 분류하세요.
- 판단이 애매하면 [판단보류]로 하고 이유를 적으세요.
- 반드시 아래 JSON 형식으로만, 다른 말 없이 답하세요.
{"분류":"실패수요|가치수요|기타|판단보류", "세부사유":"한 줄 요약", "근거":"판단 이유 한 문장", "확신도":0~100}

분류할 문장:
"""

VALID_CATEGORIES = {"실패수요", "가치수요", "기타", "판단보류"}

# 모델이 영문 키를 쓸 때를 대비한 매핑
_KEY_MAP = {
    "category":       "분류",
    "class":          "분류",
    "classification": "분류",
    "type":           "분류",
    "label":          "분류",
    "reason":         "세부사유",
    "detail":         "세부사유",
    "sub_reason":     "세부사유",
    "summary":        "세부사유",
    "basis":          "근거",
    "evidence":       "근거",
    "explanation":    "근거",
    "rationale":      "근거",
    "confidence":     "확신도",
    "score":          "확신도",
    "certainty":      "확신도",
}

# 모델이 영문 분류값을 쓸 때를 대비한 매핑
_CAT_MAP = {
    "failure":        "실패수요",
    "failure_demand": "실패수요",
    "실패":           "실패수요",
    "value":          "가치수요",
    "value_demand":   "가치수요",
    "가치":           "가치수요",
    "other":          "기타",
    "others":         "기타",
    "pending":        "판단보류",
    "uncertain":      "판단보류",
    "undecided":      "판단보류",
}


def _normalize_parsed(parsed: dict) -> dict:
    """영문 키/값을 한국어로 정규화"""
    result = {}
    for k, v in parsed.items():
        normalized_key = _KEY_MAP.get(k.lower(), k)
        result[normalized_key] = v

    # 분류값 정규화
    cat = str(result.get("분류", "")).strip()
    result["분류"] = _CAT_MAP.get(cat.lower(), cat)
    return result


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
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def diagnose_one(text: str, model: str) -> dict:
    """진단용 — raw 응답과 파싱 과정을 모두 반환"""
    prompt = CLASSIFICATION_PROMPT + text.strip()
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=120,
        )
        http_status = resp.status_code
        try:
            resp_json = resp.json()
        except Exception as e:
            return {
                "http_status": http_status,
                "raw_response": resp.text[:500],
                "parse_error": f"응답 자체가 JSON이 아님: {e}",
                "final_result": None,
            }

        raw_text = resp_json.get("response", "")
        ollama_error = resp_json.get("error", "")

        parsed = safe_json_parse(raw_text)
        if parsed:
            parsed = _normalize_parsed(parsed)

        final = classify_one(text, model)
        return {
            "http_status":   http_status,
            "ollama_error":  ollama_error,
            "raw_response":  raw_text[:800],
            "parsed_json":   parsed,
            "final_result":  final,
        }
    except requests.exceptions.Timeout:
        return {"http_status": None, "ollama_error": "타임아웃 (120초 초과)", "raw_response": "", "parsed_json": None, "final_result": None}
    except Exception as e:
        return {"http_status": None, "ollama_error": str(e), "raw_response": "", "parsed_json": None, "final_result": None}


def classify_one(text: str, model: str, retries: int = 3) -> dict:
    """문의 1건을 분류하고 결과 dict 반환. 실패 시 '분류실패' 반환."""
    prompt = CLASSIFICATION_PROMPT + text.strip()

    last_error = ""
    for attempt in range(retries):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=120,
            )

            # HTTP 오류 감지
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                continue

            resp_data = resp.json()

            # Ollama 레벨 오류 (모델 없음 등)
            if "error" in resp_data:
                last_error = resp_data["error"]
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                continue

            raw = resp_data.get("response", "")
            if not raw.strip():
                last_error = "응답이 비어 있음"
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                continue

            parsed = safe_json_parse(raw)
            if parsed:
                parsed = _normalize_parsed(parsed)
                category = parsed.get("분류", "")
                if category not in VALID_CATEGORIES:
                    category = "판단보류"
                    parsed["세부사유"] = str(parsed.get("세부사유", "")) + " [카테고리 수정됨]"

                try:
                    confidence = int(parsed.get("확신도", 50))
                    confidence = max(0, min(100, confidence))
                except (ValueError, TypeError):
                    confidence = 50

                return {
                    "분류":   category,
                    "세부사유": str(parsed.get("세부사유", ""))[:200],
                    "근거":   str(parsed.get("근거", ""))[:300],
                    "확신도": confidence,
                }

            last_error = f"JSON 파싱 실패 (응답: {raw[:100]})"

        except requests.exceptions.Timeout:
            last_error = "타임아웃 (120초 초과)"
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            continue
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            continue

    return {
        "분류":   "분류실패",
        "세부사유": last_error[:200],
        "근거":   "재시도 후에도 유효한 응답을 받지 못했습니다.",
        "확신도": 0,
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
    total = len(texts)

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
