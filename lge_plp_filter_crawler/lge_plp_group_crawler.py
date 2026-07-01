# -*- coding: utf-8 -*-
"""
LGE.COM PLP 필터 '그룹명' 크롤러
------------------------------------------------------------------
목적 : 제품 PLP 38개 각각의 필터 '그룹명'만 수집 → plp_filter_groups.json 저장
       (그룹 내 개별 옵션값은 수집하지 않음)
전제 : LGE.COM PLP는 Next.js 서버사이드 렌더링(SSR)이라 필터 그룹명이 HTML에 실려 나온다.
       접힘(lazy-load) 필터군도 '그룹명'은 정적으로 들어오므로 그룹명만 뽑으면 공백이 없다.

★ 네트워크 요건
  이 스크립트는 www.lge.co.kr 에 직접 HTTPS 요청을 보낸다.
  egress(아웃바운드) 정책이 lge.co.kr 을 허용하는 환경에서 실행해야 한다.
  (차단 환경에서는 프록시가 CONNECT 에 403 을 돌려주며 한 페이지도 받지 못한다.)

사용법:
  1) pip install requests beautifulsoup4 lxml
  2) python lge_plp_group_crawler.py
  3) 같은 폴더에 plp_filter_groups.json 이 생성/갱신된다(이어쓰기).

parse_filter_groups() 의 선택자는 실제 HTML 구조를 보고 확정한다.
전략 1(DOM 선택자)과 전략 2(__NEXT_DATA__ JSON) 두 경로를 모두 시도한다.
"""

import json
import time
import re
import pathlib
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

OUT = pathlib.Path(__file__).with_name("plp_filter_groups.json")

# 제품 PLP 38개 (소모품/구독/B2B새창/브랜드소개 제외) — "대분류 > 카테고리": URL
PLP = {
    "TV/오디오 > TV": "https://www.lge.co.kr/tvs",
    "TV/오디오 > 스탠바이미": "https://www.lge.co.kr/stan-by-me",
    "TV/오디오 > 프로젝터": "https://www.lge.co.kr/projectors",
    "TV/오디오 > 오디오": "https://www.lge.co.kr/home-audio",
    "TV/오디오 > 사이니지": "https://www.lge.co.kr/displays",
    "TV/오디오 > 마인드웰니스": "https://www.lge.co.kr/mindwellness",
    "PC/모니터 > 노트북": "https://www.lge.co.kr/notebook",
    "PC/모니터 > 일체형/데스크톱/태블릿": "https://www.lge.co.kr/all-in-one-pc-and-desktop",
    "PC/모니터 > 모니터": "https://www.lge.co.kr/monitors",
    "주방가전 > 냉장고": "https://www.lge.co.kr/refrigerators",
    "주방가전 > 컨버터블 패키지": "https://www.lge.co.kr/convertible-refrigerators",
    "주방가전 > 김치냉장고": "https://www.lge.co.kr/kimchi-refrigerators",
    "주방가전 > 와인셀러": "https://www.lge.co.kr/winecellar",
    "주방가전 > 전기레인지": "https://www.lge.co.kr/electric-ranges",
    "주방가전 > 식기세척기": "https://www.lge.co.kr/dishwashers",
    "주방가전 > 광파오븐/전자레인지": "https://www.lge.co.kr/microwaves-and-ovens",
    "주방가전 > 정수기": "https://www.lge.co.kr/water-purifiers",
    "주방가전 > 맥주제조기": "https://www.lge.co.kr/lg-homebrew",
    "주방가전 > 텀블러 세척기": "https://www.lge.co.kr/tumbler-cleaner",
    "생활가전 > 워시타워": "https://www.lge.co.kr/wash-tower",
    "생활가전 > 워시콤보": "https://www.lge.co.kr/wash-combo",
    "생활가전 > 세탁기": "https://www.lge.co.kr/washing-machines",
    "생활가전 > 의류건조기": "https://www.lge.co.kr/dryers",
    "생활가전 > 의류관리기": "https://www.lge.co.kr/lg-styler",
    "생활가전 > 시스템아이어닝": "https://www.lge.co.kr/system-ironing",
    "생활가전 > 신발관리기": "https://www.lge.co.kr/shoe-care",
    "생활가전 > 안마의자": "https://www.lge.co.kr/massage-chairs",
    "생활가전 > 청소기": "https://www.lge.co.kr/vacuum-cleaners",
    "생활가전 > 식물생활가전": "https://www.lge.co.kr/lg-tiiun",
    "에어컨/에어케어 > 에어컨": "https://www.lge.co.kr/air-conditioners",
    "에어컨/에어케어 > 시스템 에어컨": "https://www.lge.co.kr/system-air-conditioners",
    "에어컨/에어케어 > 공기청정기": "https://www.lge.co.kr/air-purifier",
    "에어컨/에어케어 > 제습기": "https://www.lge.co.kr/dehumidifiers",
    "에어컨/에어케어 > 선풍기": "https://www.lge.co.kr/fan",
    "에어컨/에어케어 > 가습기": "https://www.lge.co.kr/humidifiers",
    "에어컨/에어케어 > 환기 시스템": "https://www.lge.co.kr/ventilation-system",
    "에어컨/에어케어 > 바스에어시스템": "https://www.lge.co.kr/bath-air-system",
    "AI Home > AI Home 제품": "https://www.lge.co.kr/home-iot-product",
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
}

# 필터가 아닌, 흔히 섞여 들어오는 비-필터 라벨(제외 리스트).
NOISE = {
    "추천순", "낮은가격순", "높은가격순", "신상품순", "리뷰순", "판매량순", "인기순",
    "필터", "정렬", "전체", "적용", "초기화", "닫기", "선택됨", "비교하기", "더보기",
    "옵션", "옵션선택", "검색", "상품", "전체보기", "접기", "펼치기",
}


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=2,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(HEADERS)
    return s


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def _accept(name: str) -> bool:
    name = _clean(name)
    if not name or name in NOISE:
        return False
    # 그룹명은 짧은 한글/영문 라벨. 옵션값/문장/가격표기는 배제.
    if not (1 <= len(name) <= 20):
        return False
    if any(ch.isdigit() for ch in name) and "가격" not in name and "효율" not in name:
        # 숫자가 든 라벨은 대개 옵션값(용량 500L 등). 단 '가격/효율' 류는 그룹명일 수 있어 예외.
        return name in {"3D"}  # 사실상 배제
    return True


def _dedup(seq):
    return list(dict.fromkeys(seq))


def parse_filter_groups(html: str) -> list:
    """PLP HTML에서 필터 '그룹명' 리스트를 반환. 전략 1(DOM) → 전략 2(__NEXT_DATA__)."""
    soup = BeautifulSoup(html, "lxml")

    # --- 전략 1: DOM에서 필터 패널의 그룹 제목 추출 ---
    candidates = [
        "section[class*='filter'] [class*='title']",
        "div[class*='filter'] [class*='tit']",
        "aside[class*='filter'] button",
        "[class*='filterGroup'] [class*='name']",
        "[class*='filter'] [class*='accordion'] [class*='title']",
        "[class*='filter'] [class*='depth'] > [class*='tit']",
        "[class*='facet'] [class*='title']",
        "[class*='refinement'] [class*='title']",
    ]
    for sel in candidates:
        names = [_clean(n.get_text(" ", strip=True)) for n in soup.select(sel)]
        names = [n for n in names if _accept(n)]
        names = _dedup(names)
        if 3 <= len(names) <= 20:
            return names

    # --- 전략 2: __NEXT_DATA__ JSON에서 필터 정의 탐색 ---
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            data = json.loads(tag.string)
            found = []
            group_keys = ("filters", "facets", "filtergroups", "filterlist",
                          "filtergroup", "refinements", "attributes")

            def walk(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k.lower() in group_keys and isinstance(v, list):
                            for it in v:
                                if isinstance(it, dict):
                                    nm = (it.get("name") or it.get("title")
                                          or it.get("label") or it.get("displayName")
                                          or it.get("groupName"))
                                    if nm:
                                        found.append(_clean(str(nm)))
                        else:
                            walk(v)
                elif isinstance(obj, list):
                    for it in obj:
                        walk(it)

            walk(data)
            found = _dedup([x for x in found if _accept(x)])
            if found:
                return found
        except Exception:
            pass

    return []  # 둘 다 실패하면 빈 리스트 (선택자 보정 후 재실행)


def main():
    out = {}
    if OUT.exists():
        out = json.loads(OUT.read_text(encoding="utf-8"))

    sess = _session()
    for i, (key, url) in enumerate(PLP.items(), 1):
        if key in out and out[key].get("filter_groups"):
            print(f"[{i:>2}/38] skip (이미 있음): {key}")
            continue
        try:
            r = sess.get(url, timeout=30)
            r.raise_for_status()
            groups = parse_filter_groups(r.text)
            out[key] = {"url": url, "filter_groups": groups}
            status = f"{len(groups)}개 그룹" if groups else "★그룹 추출 실패(선택자 보정 필요)"
            print(f"[{i:>2}/38] {key} -> {status}")
        except Exception as e:
            out[key] = {"url": url, "filter_groups": out.get(key, {}).get("filter_groups", []), "error": str(e)}
            print(f"[{i:>2}/38] {key} -> 오류: {e}")

        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(1.0)

    done = sum(1 for v in out.values() if v.get("filter_groups"))
    total_groups = sum(len(v.get("filter_groups", [])) for v in out.values())
    print(f"\n완료: {done}/38 카테고리, 총 {total_groups}개 그룹명 (파일: {OUT.resolve()})")


if __name__ == "__main__":
    main()
