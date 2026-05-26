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


def check_ollama() -> tuple[bool, str]:
    """Ollama 실행 여부 확인"""
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
    """설치된 모델 목록 반환"""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def classify_one(text: str, model: str, retries: int = 3) -> dict:
    """문의 1건을 분류하고 결과 dict 반환. 실패 시 '분류실패' 반환."""
    prompt = CLASSIFICATION_PROMPT + text.strip()

    for attempt in range(retries):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=120,
            )
            raw = resp.json().get("response", "")
            parsed = safe_json_parse(raw)

            if parsed:
                category = parsed.get("분류", "")
                if category not in VALID_CATEGORIES:
                    category = "판단보류"
                    parsed["세부사유"] = parsed.get("세부사유", "") + " [카테고리 수정됨]"

                try:
                    confidence = int(parsed.get("확신도", 50))
                    confidence = max(0, min(100, confidence))
                except (ValueError, TypeError):
                    confidence = 50

                return {
                    "분류": category,
                    "세부사유": str(parsed.get("세부사유", ""))[:200],
                    "근거": str(parsed.get("근거", ""))[:300],
                    "확신도": confidence,
                }

        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            continue
        except Exception:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            continue

    return {
        "분류": "분류실패",
        "세부사유": "LLM 응답 파싱 실패",
        "근거": "재시도 후에도 유효한 JSON 응답을 받지 못했습니다.",
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
    """
    여러 건 순차 분류.
    progress_callback(current, total) — 진행률 UI 업데이트용
    stop_flag — [False] 형태의 리스트; True 로 바뀌면 중단
    checkpoint_callback(results_so_far) — 중간 저장용
    """
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
