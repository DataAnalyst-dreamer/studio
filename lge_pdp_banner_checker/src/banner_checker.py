"""Playwright 기반 배너 노출 점검 모듈.

모바일 viewport(Chromium)로 각 PDP URL에 접속하여 대상 배너 이미지가
DOM에 존재하는지, visible인지, naturalWidth/Height가 0보다 큰지를 확인하고
PASS/WARN/FAIL/EXCLUDED로 분류한다(PRD 9 / FR-006).

- 개별 URL 오류가 전체 점검을 중단시키지 않는다(try/except로 격리).
- 동시성은 asyncio.Semaphore로 제어하며 기본 3 이하로 제한한다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Optional

import pandas as pd

from .config import (
    DEFAULT_DEVICE_SCALE_FACTOR,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT,
)
from .data_preprocess import classify_url

# 결과 상태 (PRD 9.2)
STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_EXCLUDED = "EXCLUDED"

# 시스템 점검 페이지 감지 키워드 (검토문서 / PRD 15)
MAINTENANCE_KEYWORDS = ("시스템 점검", "일시적으로", "working.html", "잠시 후 다시")

# 점검 결과 상세 컬럼 (PRD 11.2)
RESULT_FIELDS = [
    "checked_at",
    "category",
    "catg_lvl1_nm",
    "catg_lvl2_nm",
    "catg_lvl3_nm",
    "sku",
    "clean_page_url",
    "vsit_pagenm",
    "status",
    "reason",
    "http_status",
    "final_url",
    "image_found",
    "is_visible",
    "natural_width",
    "natural_height",
    "current_src",
    "alt",
    "elapsed_ms",
    "error_message",
]

# 입력 카테고리/식별 컬럼
_PASSTHROUGH_COLS = [
    "category",
    "catg_lvl1_nm",
    "catg_lvl2_nm",
    "catg_lvl3_nm",
    "sku",
    "clean_page_url",
    "vsit_pagenm",
]


@dataclass
class CheckResult:
    """단일 URL 점검 결과."""

    status: str = STATUS_FAIL
    reason: str = ""
    http_status: Optional[int] = None
    final_url: str = ""
    image_found: bool = False
    is_visible: bool = False
    natural_width: int = 0
    natural_height: int = 0
    current_src: str = ""
    alt: str = ""
    elapsed_ms: int = 0
    error_message: str = ""
    extra: dict = field(default_factory=dict)

    def as_record(self, row: dict) -> dict:
        record = {col: row.get(col, "") for col in _PASSTHROUGH_COLS}
        record.update(
            {
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "status": self.status,
                "reason": self.reason,
                "http_status": self.http_status,
                "final_url": self.final_url,
                "image_found": self.image_found,
                "is_visible": self.is_visible,
                "natural_width": self.natural_width,
                "natural_height": self.natural_height,
                "current_src": self.current_src,
                "alt": self.alt,
                "elapsed_ms": self.elapsed_ms,
                "error_message": self.error_message,
            }
        )
        return record


def classify_banner(
    image_found: bool,
    is_visible: bool,
    natural_width: int,
    natural_height: int,
) -> tuple[str, str]:
    """배너 검사 결과를 PASS/WARN/FAIL로 분류한다(PRD 9.2).

    - PASS : DOM 존재 + visible + naturalWidth/Height > 0
    - WARN : DOM 존재하나 visible 아니거나 로드 불완전
    - FAIL : DOM에 이미지 없음
    """
    if not image_found:
        return STATUS_FAIL, "BANNER_DOM_NOT_FOUND"

    loaded = natural_width > 0 and natural_height > 0
    if is_visible and loaded:
        return STATUS_PASS, "BANNER_VISIBLE_AND_LOADED"

    if not is_visible:
        return STATUS_WARN, "BANNER_FOUND_BUT_NOT_VISIBLE"
    return STATUS_WARN, "BANNER_FOUND_BUT_NOT_LOADED"


def _is_maintenance(body_text: str, final_url: str) -> bool:
    haystack = f"{body_text} {final_url}".lower()
    return any(kw.lower() in haystack for kw in MAINTENANCE_KEYWORDS)


async def _check_single(
    context,
    row: dict,
    banner_image_path: str,
    timeout_ms: int,
) -> CheckResult:
    """단일 PDP URL을 점검한다. 모든 예외는 내부에서 격리된다."""
    result = CheckResult()
    url = str(row.get("clean_page_url", "")).strip()
    selector = f'img[src*="{banner_image_path}"]'

    start = datetime.now()
    page = None
    try:
        page = await context.new_page()
        response = await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        result.http_status = response.status if response else None
        result.final_url = page.url

        # 시스템 점검/오류 페이지 감지
        try:
            body_text = await page.locator("body").inner_text(timeout=5000)
        except Exception:  # noqa: BLE001
            body_text = ""
        if _is_maintenance(body_text, page.url):
            result.status = STATUS_FAIL
            result.reason = "SITE_MAINTENANCE"
            return result

        # lazy-load 대응: 페이지를 단계적으로 스크롤하며 배너 등장 확인
        for offset in (600, 1200, 1800, 2600, 3600, 5000):
            if await page.locator(selector).count() > 0:
                break
            await page.mouse.wheel(0, offset)
            await page.wait_for_timeout(400)

        locator = page.locator(selector)
        count = await locator.count()
        result.image_found = count > 0

        if not result.image_found:
            result.status = STATUS_FAIL
            result.reason = "BANNER_DOM_NOT_FOUND"
            return result

        first = locator.first
        try:
            result.is_visible = await first.is_visible()
        except Exception:  # noqa: BLE001
            result.is_visible = False

        try:
            result.natural_width = int(
                await first.evaluate("(img) => img.naturalWidth || 0")
            )
            result.natural_height = int(
                await first.evaluate("(img) => img.naturalHeight || 0")
            )
        except Exception:  # noqa: BLE001
            result.natural_width = 0
            result.natural_height = 0

        result.current_src = (await first.get_attribute("src")) or ""
        result.alt = (await first.get_attribute("alt")) or ""

        status, reason = classify_banner(
            result.image_found,
            result.is_visible,
            result.natural_width,
            result.natural_height,
        )
        result.status = status
        result.reason = reason

    except Exception as exc:  # noqa: BLE001 - 개별 URL 오류 격리(AC-009)
        result.status = STATUS_FAIL
        result.reason = "CHECK_ERROR"
        result.error_message = str(exc)[:300]
    finally:
        result.elapsed_ms = int(
            (datetime.now() - start).total_seconds() * 1000
        )
        if page is not None:
            try:
                await page.close()
            except Exception:  # noqa: BLE001
                pass

    return result


async def check_banners_async(
    targets: pd.DataFrame,
    banner_image_path: str,
    concurrency: int = 3,
    timeout_ms: int = 30000,
    viewport: Optional[dict] = None,
    user_agent: str = DEFAULT_USER_AGENT,
    device_scale_factor: int = DEFAULT_DEVICE_SCALE_FACTOR,
    excluded: Optional[pd.DataFrame] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """대상 DataFrame을 모바일 렌더링으로 점검하여 결과 DataFrame을 반환한다.

    excluded DataFrame이 주어지면 EXCLUDED 상태로 결과에 합쳐진다.
    """
    from playwright.async_api import async_playwright

    viewport = viewport or dict(DEFAULT_VIEWPORT)
    concurrency = max(1, min(int(concurrency), 3))

    records: list[dict] = []

    # EXCLUDED 행 먼저 기록 (점검하지 않음)
    if excluded is not None and not excluded.empty:
        for _, row in excluded.iterrows():
            row_dict = row.to_dict()
            reason = str(row_dict.get("exclude_reason", "") or "NON_PDP_URL")
            cr = CheckResult(status=STATUS_EXCLUDED, reason=reason)
            records.append(cr.as_record(row_dict))

    rows = [r.to_dict() for _, r in targets.iterrows()] if targets is not None and not targets.empty else []
    total = len(rows)
    done = 0

    if total > 0:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport=viewport,
                is_mobile=True,
                device_scale_factor=device_scale_factor,
                user_agent=user_agent,
            )
            semaphore = asyncio.Semaphore(concurrency)
            lock = asyncio.Lock()

            async def _worker(row: dict) -> dict:
                nonlocal done
                async with semaphore:
                    cr = await _check_single(
                        context, row, banner_image_path, timeout_ms
                    )
                record = cr.as_record(row)
                async with lock:
                    done += 1
                    if progress_callback:
                        progress_callback(done, total)
                return record

            try:
                worker_results = await asyncio.gather(
                    *[_worker(row) for row in rows]
                )
                records.extend(worker_results)
            finally:
                await context.close()
                await browser.close()

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=RESULT_FIELDS)
    # 컬럼 순서 보장
    for col in RESULT_FIELDS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[RESULT_FIELDS]


def run_banner_check(
    targets: pd.DataFrame,
    banner_image_path: str,
    concurrency: int = 3,
    timeout_ms: int = 30000,
    viewport: Optional[dict] = None,
    user_agent: str = DEFAULT_USER_AGENT,
    device_scale_factor: int = DEFAULT_DEVICE_SCALE_FACTOR,
    excluded: Optional[pd.DataFrame] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """check_banners_async의 동기 래퍼.

    Streamlit 등 동기 컨텍스트에서 호출하기 위한 진입점이다.
    """
    return asyncio.run(
        check_banners_async(
            targets=targets,
            banner_image_path=banner_image_path,
            concurrency=concurrency,
            timeout_ms=timeout_ms,
            viewport=viewport,
            user_agent=user_agent,
            device_scale_factor=device_scale_factor,
            excluded=excluded,
            progress_callback=progress_callback,
        )
    )
