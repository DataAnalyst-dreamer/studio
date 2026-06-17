#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LGE.COM 고객 Q&A 자동 분류 앱 V4
기존 유형 분류 + 가치수요 / 실패수요 구분 추가
CSV/Excel 지원 (CP949 인코딩 포함)

실행 방법: python QNA_Classifier_V4.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import re
import warnings
warnings.filterwarnings('ignore')

try:
    import pandas as pd
    import numpy as np
    import joblib
    from datetime import datetime
except ImportError as e:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("라이브러리 오류",
        f"필요한 라이브러리가 없습니다:\n{e}\n\n"
        "명령 프롬프트에서 실행:\n"
        "pip install pandas numpy scikit-learn joblib")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────
# 1. 전처리
# ──────────────────────────────────────────────────────────────

class TextPreprocessor:
    def __init__(self):
        self.synonym_dict = {
            r'lg전자|엘지전자|엘쥐': 'lg',
            r'냉장고|김치냉장고|김냉': '냉장고',
            r'세탁기|워시타워|트롬': '세탁기',
            r'에어컨|휘센': '에어컨',
            r'정수기|퓨리케어': '정수기',
            r'식기세척기|식세기': '식기세척기',
            r'청소기|코드제로': '청소기',
            r'tv|티비|텔레비전': 'tv',
            r'올레드|oled': '올레드tv',
            r'사운드바|사운드 바|soundbar': '사운드바',
            r'인덕션|하이라이트|전기레인지': '인덕션',
            r'엘리베이터|엘베': '엘리베이터',
            r'씽큐|thinq': '씽큐',
        }

    def preprocess(self, text):
        if pd.isna(text) or text is None:
            return ""
        text = str(text).lower()
        text = re.sub(r'<[^>]+>', '', text)
        for pattern, replacement in self.synonym_dict.items():
            text = re.sub(pattern, replacement, text)
        return text


# ──────────────────────────────────────────────────────────────
# 2. 기존 유형 분류 (규칙 기반, V3 확장)
# ──────────────────────────────────────────────────────────────

class RuleBasedClassifier:
    def __init__(self):
        self.patterns = {
            # 주문
            '주문_취소변경':    r'(주문.*취소|취소.*해주|주문취소|옵션.*변경|색상.*변경|취소.*요청)',
            '주문_내역확인':    r'(내역서|명세서|영수증|구매.*확인서|주문.*확인|결제.*내역|세금계산서|현금영수증)',

            # 소모품/부품
            '소모품_필터':      r'(필터.*구매|필터.*교체|필터.*사[고려]|헤파필터|탈취필터|에어필터|필터.*가격|필터.*구입)',
            '소모품_리모컨':    r'(리모컨.*구매|리모컨.*사[고려]|리모컨.*추가|리모콘|매직리모컨|리모컨.*호환|리모컨.*구입)',
            '소모품_부품':      r'(운모판|유리판|선반.*구[매입]|트레이.*구[매입]|호스.*구[매입]|받침대.*구[매입]|스탠드.*구[매입]|부품.*구[매입]|소모품.*구[매입]|부속품)',

            # 구독
            '구독_계약소유권':  r'(소유권|인수|만기|해지|약정.*기간|계약.*종료|계약.*만료|렌탈.*종료|구독.*종료|철회|위약금)',
            '구독_요금':        r'(구독료|월.*요금|렌탈료|구독.*비용|구독.*가격|렌탈.*비용|월렌탈|구독.*할인|렌탈.*요금)',
            '구독_케어서비스':  r'(케어.*서비스|케어십|케어솔루션|정기.*관리|방문.*관리|필터.*무상|정기.*점검)',

            # AS/서비스
            'AS_수리고장':      r'(고장|수리|as신청|a\/s신청|as접수|서비스.*신청|작동.*안|안됨|안되|망가|파손|불량|오류|에러|멈춤|꺼짐|안켜|냉수.*안|온수.*안|얼음.*안)',
            'AS_교환반품':      r'(교환.*신청|반품.*신청|환불|교환.*요청|반품.*요청|교환해|반품해)',
            'AS_폐가전':        r'(폐가전|회수.*신청|수거.*신청|가져가|철거|폐기)',
            'AS_제조일보증':    r'(제조.*일|제조.*년|생산.*일|년식|보증.*기간|무상.*기간|워런티|제조년월)',

            # 설치/사이즈
            '설치_호환성':      r'(호환.*되|호환.*가능|호환.*되나|연결.*가능|같이.*설치|세트.*설치|조합|매칭|맞는|스태킹|키트|같이.*쓸)',
            '설치_사이즈':      r'(사이즈|크기.*문의|치수|높이.*문의|폭.*문의|너비|가로.*세로|간격|여유.*공간|설치.*공간)',
            '설치_조건':        r'(설치.*조건|콘센트|전기.*용량|220v|110v|접지|배수|급수|환기|배기)',
            '설치_이동반입':    r'(현관|엘리베이터|계단|입구|반입|올릴|들어갈|사다리차|이사)',
            '설치_일반':        r'(설치.*가능|설치.*되나|설치.*문의|설치.*방법|벽걸이.*설치|빌트인|직접.*설치|셀프.*설치)',
            '설치_비용':        r'(설치.*비용|설치비|설치.*유료|설치.*무료|사다리.*비용)',

            # 배송
            '배송_일정확인':    r'(배송.*언제|언제.*도착|언제.*받|배송.*예정|배송일|도착.*예정|며칠|배송.*기간|배송.*확인)',
            '배송_일정변경':    r'(배송.*변경|배송.*연기|날짜.*변경|배송.*지정|희망.*날짜|배송.*앞당|빨리.*받)',
            '배송_재입고':      r'(재입고|품절|재고.*없|입고.*예정|언제.*들어|출시.*예정|판매.*재개|재고.*확인)',
            '배송_방법비용':    r'(배송.*비용|배송비|배송.*유료|배송.*무료|택배비|무료배송|배송만|설치.*없이)',

            # 프로모션
            '프로모션_할인혜택':     r'(할인.*정보|할인.*언제|쿠폰|캐시백|카드.*혜택|카드.*할인|무이자|청약|으뜸효율|환급)',
            '프로모션_포인트':       r'(포인트.*지급|포인트.*적립|포인트.*언제|리뷰.*포인트|포인트.*사용|적립금)',
            '프로모션_이벤트사은품': r'(이벤트|라방|라이브.*방송|사은품|증정품|경품|추첨|당첨|선착순|타임딜|특가)',

            # 스펙/기능
            '스펙_기능사용법':  r'(기능.*문의|어떻게.*사용|사용.*방법|사용법|설정.*방법|모드.*사용|작동.*방법)',
            '스펙_비교':        r'(차이점|차이.*뭐|비교|다른점|vs|어떤.*다른|뭐가.*다름|어떤게.*좋|모델.*차이)',
            '스펙_ThinQ연동':   r'(씽큐|앱.*연동|스마트.*연동|wifi.*연결|와이파이|블루투스|스마트홈|앱.*연결)',
            '스펙_소음성능':    r'(소음|데시벨|db|시끄러|조용|진동|성능|소비전력|전력|와트|효율|전기세)',
            '스펙_색상디자인':  r'(색상|컬러|화이트|블랙|실버|베이지|색깔|디자인|외관)',
            '스펙_구성품':      r'(구성품|포함.*되|같이.*오|함께.*오|동봉|기본.*제공)',

            # 제품별 특화
            '제품_냉장냉동':    r'(냉장.*온도|냉동.*온도|온도.*조절|냉각|얼음|제빙|급속.*냉동|냉기|성에|냉장.*용량)',
            '제품_세탁건조':    r'(세탁.*코스|건조.*코스|탈수|헹굼|세제.*투입|건조.*시간|세탁.*시간|드럼|통돌이|울코스)',
            '제품_에어컨':      r'(냉방|난방|제습|바람|온도.*설정|실외기|에어컨.*청소|냉매|인버터|청정)',
            '제품_TV모니터':    r'(화질|해상도|화면.*크기|채널|올레드tv|화면.*설정|타임머신|녹화|hdmi|자동.*꺼|절전|패널|게임.*모드|hdr|돌비|자막|음성.*출력|스크린|입력)',
            '제품_사운드바':    r'(사운드바|광단자|hdmi.*arc|서라운드|돌비.*사운드|사운드.*모드)',
            '제품_인덕션':      r'(인덕션|화구|불.*조절|인덕션.*온도|안전.*잠금|인덕션.*청소|하이라이트)',
            '제품_정수기':      r'(냉수|온수|정수|필터.*교체|물.*맛|물.*냄새|살균|코크)',

            # 구매/재고
            '구매_재고단종':    r'(단종|더이상.*생산|재고.*있|재고.*확인|구할.*수|살.*수.*있|판매.*중|판매.*여부)',
            '구매_가격문의':    r'(가격.*문의|가격.*얼마|얼마.*인가|비용.*얼마|금액|견적)',
            '구매_추천':        r'(추천.*해|어떤.*좋|뭐.*좋을까|고르|선택.*도움|뭘.*사야)',
        }

        self.category_mapping = {
            '주문_취소변경': '주문관리', '주문_내역확인': '주문관리',
            '소모품_필터': '소모품/부품', '소모품_리모컨': '소모품/부품', '소모품_부품': '소모품/부품',
            '구독_계약소유권': '구독', '구독_요금': '구독', '구독_케어서비스': '구독',
            'AS_수리고장': 'AS/서비스', 'AS_교환반품': 'AS/서비스',
            'AS_폐가전': 'AS/서비스', 'AS_제조일보증': 'AS/서비스',
            '설치_호환성': '설치/사이즈', '설치_사이즈': '설치/사이즈', '설치_조건': '설치/사이즈',
            '설치_이동반입': '설치/사이즈', '설치_일반': '설치/사이즈', '설치_비용': '설치/사이즈',
            '배송_일정확인': '배송', '배송_일정변경': '배송',
            '배송_재입고': '배송', '배송_방법비용': '배송',
            '프로모션_할인혜택': '프로모션', '프로모션_포인트': '프로모션',
            '프로모션_이벤트사은품': '프로모션',
            '스펙_기능사용법': '스펙/기능', '스펙_비교': '스펙/기능',
            '스펙_ThinQ연동': '스펙/기능', '스펙_소음성능': '스펙/기능',
            '스펙_색상디자인': '스펙/기능', '스펙_구성품': '스펙/기능',
            '제품_냉장냉동': '스펙/기능', '제품_세탁건조': '스펙/기능',
            '제품_에어컨': '스펙/기능', '제품_TV모니터': '스펙/기능',
            '제품_사운드바': '스펙/기능', '제품_인덕션': '스펙/기능',
            '제품_정수기': '스펙/기능',
            '구매_재고단종': '구매/재고', '구매_가격문의': '구매/재고', '구매_추천': '구매/재고',
        }

        self.priority = {
            '주문_취소변경': 1,
            'AS_수리고장': 2, 'AS_교환반품': 2, 'AS_폐가전': 3,
            '소모품_필터': 4, '소모품_리모컨': 4, '소모품_부품': 4,
            '구독_계약소유권': 5, '구독_요금': 5, '구독_케어서비스': 5,
            'AS_제조일보증': 6,
            '배송_일정확인': 7, '배송_일정변경': 7,
            '배송_재입고': 8, '배송_방법비용': 8,
            '프로모션_할인혜택': 9, '프로모션_포인트': 9, '프로모션_이벤트사은품': 9,
            '주문_내역확인': 10,
            '설치_호환성': 11, '설치_사이즈': 11, '설치_조건': 11,
            '설치_이동반입': 11, '설치_비용': 12, '설치_일반': 13,
            '스펙_기능사용법': 14, '스펙_비교': 14, '스펙_ThinQ연동': 14,
            '스펙_소음성능': 14, '스펙_색상디자인': 14, '스펙_구성품': 14,
            '제품_냉장냉동': 15, '제품_세탁건조': 15, '제품_에어컨': 15,
            '제품_TV모니터': 15, '제품_사운드바': 15, '제품_인덕션': 15,
            '제품_정수기': 15,
            '구매_재고단종': 16, '구매_가격문의': 16, '구매_추천': 16,
        }

    def classify(self, text):
        text = str(text).lower()
        matches = []
        for category, pattern in self.patterns.items():
            if re.search(pattern, text):
                priority = self.priority.get(category, 99)
                matches.append((category, priority))

        if matches:
            matches.sort(key=lambda x: x[1])
            best_match = matches[0][0]
            return {
                '세부분류': best_match,
                '대분류': self.category_mapping.get(best_match, '기타'),
                '신뢰도': 0.9,
            }
        return {'세부분류': '기타', '대분류': '기타', '신뢰도': 0.0}


# ──────────────────────────────────────────────────────────────
# 3. 가치수요 / 실패수요 판별
# ──────────────────────────────────────────────────────────────

class DemandTypeClassifier:
    """
    Seddon 프레임워크 기반:
    "회사가 일을 완벽히 했어도 고객이 이 질문을 했을까?"
      → 예 = 가치수요 / 아니오 = 실패수요
    """

    # 세부분류 → (수요유형, 수요세부분류) 기본 매핑
    BASE_MAPPING = {
        # 실패수요 계열
        'AS_수리고장':       ('실패수요', 'AS처리지연'),
        'AS_교환반품':       ('실패수요', '오배송/파손'),

        # 가치수요 계열
        'AS_제조일보증':     ('가치수요', 'AS사전문의'),
        'AS_폐가전':         ('기타',     '해당없음'),
        '소모품_필터':       ('가치수요', '사용방법'),
        '소모품_리모컨':     ('가치수요', '사용방법'),
        '소모품_부품':       ('가치수요', '사용방법'),
        '구독_계약소유권':   ('가치수요', 'AS사전문의'),
        '구독_요금':         ('가치수요', '가격/혜택'),
        '구독_케어서비스':   ('가치수요', '사용방법'),
        '배송_일정확인':     ('가치수요', '구매상담'),  # 지연 키워드 있으면 실패수요로 override
        '배송_일정변경':     ('기타',     '해당없음'),
        '배송_재입고':       ('가치수요', '구매상담'),
        '배송_방법비용':     ('가치수요', '구매상담'),
        '주문_취소변경':     ('기타',     '해당없음'),
        '주문_내역확인':     ('가치수요', '구매상담'),
        '설치_호환성':       ('가치수요', '스펙/호환성'),
        '설치_사이즈':       ('가치수요', '스펙/호환성'),
        '설치_조건':         ('가치수요', '설치조건'),
        '설치_이동반입':     ('가치수요', '설치조건'),
        '설치_비용':         ('가치수요', '설치조건'),
        '설치_일반':         ('가치수요', '설치조건'),  # 기사 미방문 키워드 있으면 override
        '프로모션_할인혜택': ('가치수요', '가격/혜택'),
        '프로모션_포인트':   ('가치수요', '가격/혜택'),
        '프로모션_이벤트사은품': ('가치수요', '가격/혜택'),
        '스펙_기능사용법':   ('가치수요', '사용방법'),
        '스펙_비교':         ('가치수요', '구매상담'),
        '스펙_ThinQ연동':    ('가치수요', '사용방법'),
        '스펙_소음성능':     ('가치수요', '스펙/호환성'),
        '스펙_색상디자인':   ('가치수요', '구매상담'),
        '스펙_구성품':       ('가치수요', '스펙/호환성'),
        '제품_냉장냉동':     ('가치수요', '사용방법'),
        '제품_세탁건조':     ('가치수요', '사용방법'),
        '제품_에어컨':       ('가치수요', '사용방법'),
        '제품_TV모니터':     ('가치수요', '사용방법'),
        '제품_사운드바':     ('가치수요', '사용방법'),
        '제품_인덕션':       ('가치수요', '사용방법'),
        '제품_정수기':       ('가치수요', '사용방법'),
        '구매_재고단종':     ('가치수요', '구매상담'),
        '구매_가격문의':     ('가치수요', '가격/혜택'),
        '구매_추천':         ('가치수요', '구매상담'),
        '기타':              ('기타',     '해당없음'),
    }

    # 텍스트에 이 패턴이 있으면 실패수요로 오버라이드
    FAILURE_PATTERNS = [
        # (regex, 수요세부분류)
        # ─ 배송지연 ─
        (r'배송.*지연|배송.*늦|아직.*안\s*왔|아직.*못\s*받|배송.*추적.*안|아직도.*배송|배송.*없어', '배송지연'),
        # ─ 오배송/파손 ─
        (r'배송.*안\s*왔|택배.*안\s*왔|택배.*없는|누락.*배송|오배송|다른.*상품.*왔|잘못.*왔|상품이.*안\s*왔', '오배송/파손'),
        (r'파손|훼손|찌그러|깨진.*채로|부서|망가진.*채|박스.*찌그', '오배송/파손'),
        # ─ 시스템오류 (결제창보다 먼저 체크) ─
        (r'결제창.*오류|결제창.*에러|결제창.*안\s*됩|사이트.*오류|사이트.*안\s*됩|앱.*오류|앱.*에러|앱.*안\s*됩|앱.*안\s*됨|앱.*안\s*열|로그인.*안\s*됩|로그인.*안\s*됨|주문.*안\s*됩|씽큐.*오류|씽큐.*에러|씽큐.*안\s*됩|씽큐.*안\s*됨', '시스템오류'),
        # ─ 결제/환불오류 ─
        (r'이중.*결제|중복.*결제|결제.*실패|결제.*오류|결제.*안\s*됩|결제.*안\s*됨', '결제/환불오류'),
        (r'환불.*안|환불.*지연|환불.*못|환불.*언제.*받|포인트.*안.*적립|포인트.*지연|포인트.*없어', '결제/환불오류'),
        (r'요금.*잘못|잘못.*청구|이중.*청구|요금.*오류|구독료.*왜|렌탈료.*오류', '결제/환불오류'),
        # ─ 상품정보불일치 ─
        (r'상품.*설명.*다르|상품.*설명.*달라|사진.*다르|사진.*달라|실제.*다르|실제.*달라|스펙.*다르|스펙.*달라|정보.*다르|정보.*달라|광고.*다른|기재.*오류', '상품정보불일치'),
        # ─ 설치/기사미흡 ─
        (r'설치.*안\s*왔|기사.*안\s*왔|기사.*안\s*나타|설치.*취소|기사.*연락.*없|설치.*미뤄|방문.*안|기사.*노쇼', '설치/기사미흡'),
        (r'설치.*불량|설치.*잘못|설치.*제대로|설치.*하자|설치.*다시', '설치/기사미흡'),
        # ─ CS응대불만 ─
        (r'상담사.*불친|답변.*늦|연락.*안\s*됨|연락.*닿지|cs.*불만|응대.*불만|불친절|무시.*당|답답', 'CS응대불만'),
        # ─ AS처리지연 ─
        (r'as.*지연|as.*안\s*됨|수리.*지연|수리.*오래|수리.*언제|접수.*안\s*됨|수리.*불량|수리.*다시', 'AS처리지연'),
    ]

    def classify(self, subcat: str, text: str):
        """
        Returns (수요유형, 수요세부분류) tuple
        """
        text_lower = str(text).lower() if text else ""

        # 키워드 기반 실패수요 오버라이드 (텍스트 우선)
        for pattern, demand_subcat in self.FAILURE_PATTERNS:
            if re.search(pattern, text_lower):
                return ('실패수요', demand_subcat)

        # 기본 매핑
        return self.BASE_MAPPING.get(subcat, ('기타', '해당없음'))


# ──────────────────────────────────────────────────────────────
# 4. 통합 분류기
# ──────────────────────────────────────────────────────────────

class HybridClassifier:
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.rule_classifier = RuleBasedClassifier()
        self.demand_classifier = DemandTypeClassifier()
        self.ml_model = None
        self.vectorizer = None
        self.label_encoder = None
        self.model_loaded = False

    def load_model(self, model_path):
        try:
            model_data = joblib.load(model_path)
            self.ml_model = model_data['model']
            self.vectorizer = model_data['vectorizer']
            self.label_encoder = model_data['label_encoder']
            self.model_loaded = True
            return True
        except Exception:
            self.model_loaded = False
            return False

    def predict_single(self, raw_text: str) -> dict:
        processed = self.preprocessor.preprocess(raw_text)
        rule_result = self.rule_classifier.classify(processed)

        if rule_result['신뢰도'] >= 0.7:
            subcat = rule_result['세부분류']
            demand_type, demand_subcat = self.demand_classifier.classify(subcat, processed)
            return {
                '대분류': rule_result['대분류'],
                '세부분류': subcat,
                '분류방식': '규칙기반',
                '수요유형': demand_type,
                '수요세부분류': demand_subcat,
            }

        if self.model_loaded and self.ml_model is not None:
            try:
                X = self.vectorizer.transform([processed])
                pred = self.ml_model.predict(X)[0]
                ml_subcat = self.label_encoder.inverse_transform([pred])[0]
                main_cat = self.rule_classifier.category_mapping.get(ml_subcat, '스펙/기능')
                demand_type, demand_subcat = self.demand_classifier.classify(ml_subcat, processed)
                return {
                    '대분류': main_cat,
                    '세부분류': ml_subcat,
                    '분류방식': 'ML',
                    '수요유형': demand_type,
                    '수요세부분류': demand_subcat,
                }
            except Exception:
                pass

        subcat = rule_result['세부분류']
        demand_type, demand_subcat = self.demand_classifier.classify(subcat, processed)
        return {
            '대분류': rule_result['대분류'],
            '세부분류': subcat,
            '분류방식': '규칙기반',
            '수요유형': demand_type,
            '수요세부분류': demand_subcat,
        }


# ──────────────────────────────────────────────────────────────
# 5. 컬럼 탐지 헬퍼
# ──────────────────────────────────────────────────────────────

def detect_text_columns(df: pd.DataFrame):
    """
    분류에 사용할 텍스트를 구성하는 컬럼(들)을 반환.
    Returns (primary_col, secondary_col) — secondary_col은 없으면 None.
    primary_col + secondary_col 을 합쳐서 분류에 사용한다.
    """
    cols = df.columns.tolist()

    # q_full_text 단독 사용 (5월 DB 추출 포맷)
    if 'q_full_text' in cols:
        return 'q_full_text', None

    # q_title + q_cntn 조합
    if 'q_cntn' in cols:
        sec = 'q_title' if 'q_title' in cols else None
        return 'q_cntn', sec

    # 기존 포맷
    for candidate in ('상세내용', '제목', 'content', 'text', '내용', '질문', 'Content', 'Text'):
        if candidate in cols:
            return candidate, None

    # 마지막 수단: 첫 번째 object 컬럼
    for col in cols:
        if df[col].dtype == 'object':
            return col, None

    return None, None


def compose_text(row, primary_col: str, secondary_col) -> str:
    parts = []
    if secondary_col and pd.notna(row.get(secondary_col)):
        parts.append(str(row[secondary_col]))
    val = row.get(primary_col)
    if pd.notna(val) and str(val).strip():
        parts.append(str(val))
    return " ".join(parts)


# ──────────────────────────────────────────────────────────────
# 6. Tkinter UI
# ──────────────────────────────────────────────────────────────

class QNAClassifierApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LGE.COM Q&A 자동 분류 시스템 V4")
        self.root.geometry("680x580")
        self.root.resizable(False, False)

        self.input_file = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.status_text = tk.StringVar(value="파일을 선택해주세요.")
        self.progress_var = tk.DoubleVar(value=0)

        self.classifier = HybridClassifier()
        self.cancel_flag = False

        self.create_widgets()
        self.find_and_load_model()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="📊 LGE.COM Q&A 자동 분류 시스템",
                  font=('맑은 고딕', 16, 'bold')).pack(pady=(0, 4))
        ttk.Label(main_frame,
                  text="V4.0 — 기존 유형 분류 + 가치/실패 수요 구분 (CSV·Excel)",
                  font=('맑은 고딕', 9), foreground='#1565C0').pack(pady=(0, 14))

        # 파일 선택
        file_frame = ttk.LabelFrame(main_frame, text="1. 분류할 파일 선택 (CSV 또는 Excel)", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Entry(file_frame, textvariable=self.input_file, width=55, state='readonly').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(file_frame, text="📁 파일 선택", command=self.select_input_file).pack(side=tk.LEFT)

        # 저장 위치
        save_frame = ttk.LabelFrame(main_frame, text="2. 결과 저장 위치 (미선택 시 원본 파일과 같은 폴더)", padding="10")
        save_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Entry(save_frame, textvariable=self.output_folder, width=55, state='readonly').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(save_frame, text="📂 폴더 선택", command=self.select_output_folder).pack(side=tk.LEFT)

        # 진행 상태
        progress_frame = ttk.LabelFrame(main_frame, text="3. 진행 상태", padding="15")
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.percent_label = ttk.Label(progress_frame, text="0%", font=('맑은 고딕', 28, 'bold'))
        self.percent_label.pack(pady=(0, 8))

        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            maximum=100, length=480, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        self.status_label = ttk.Label(progress_frame, textvariable=self.status_text, font=('맑은 고딕', 10))
        self.status_label.pack()

        # 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=14)

        self.start_btn = ttk.Button(btn_frame, text="🚀 분류 시작", command=self.start_classification, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.cancel_btn = ttk.Button(btn_frame, text="❌ 취소", command=self.cancel_classification,
                                     width=20, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=10)

        # 하단 상태 레이블
        self.model_status = ttk.Label(main_frame, text="", font=('맑은 고딕', 9))
        self.model_status.pack(pady=(4, 0))

        self.save_path_label = ttk.Label(main_frame, text="", font=('맑은 고딕', 9),
                                         foreground='green', wraplength=640)
        self.save_path_label.pack(pady=(4, 0))

    # ── 이벤트 핸들러 ──────────────────────────────────────────

    def find_and_load_model(self):
        base_dir = (os.path.dirname(sys.executable)
                    if getattr(sys, 'frozen', False)
                    else os.path.dirname(os.path.abspath(__file__)))

        for name in ('qna_classifier_v2.pkl', 'qna_classifier_model.pkl'):
            for path in (os.path.join(base_dir, name), name):
                if os.path.exists(path):
                    if self.classifier.load_model(path):
                        self.model_status.config(
                            text=f"✅ ML 모델 로드 완료: {os.path.basename(path)}",
                            foreground='green')
                        return

        self.model_status.config(text="⚠️ ML 모델 없음 (규칙 기반으로 분류)", foreground='orange')

    def select_input_file(self):
        filetypes = [('CSV/Excel 파일', '*.csv *.xlsx'), ('CSV', '*.csv'),
                     ('Excel', '*.xlsx'), ('모든 파일', '*.*')]
        filename = filedialog.askopenfilename(title="분류할 파일 선택", filetypes=filetypes)
        if filename:
            self.input_file.set(filename)
            self.output_folder.set(os.path.dirname(filename))
            self.status_text.set("파일이 선택되었습니다. '분류 시작' 버튼을 클릭하세요.")

    def select_output_folder(self):
        folder = filedialog.askdirectory(title="결과 저장 폴더 선택")
        if folder:
            self.output_folder.set(folder)

    def update_progress(self, percent, status):
        def _update():
            self.progress_var.set(percent)
            self.percent_label.config(text=f"{percent:.0f}%")
            self.status_text.set(status)
        self.root.after(0, _update)

    def start_classification(self):
        if not self.input_file.get():
            messagebox.showwarning("경고", "분류할 파일을 선택해주세요.")
            return
        if not self.output_folder.get():
            self.output_folder.set(os.path.dirname(self.input_file.get()))

        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.cancel_flag = False

        threading.Thread(target=self.run_classification, daemon=True).start()

    def cancel_classification(self):
        self.cancel_flag = True
        self.update_progress(0, "❌ 취소 중...")

    # ── 분류 실행 (백그라운드 스레드) ─────────────────────────

    def run_classification(self):
        try:
            input_path = self.input_file.get()
            output_folder = self.output_folder.get()

            # 1. 파일 로드
            self.update_progress(5, "📂 파일 로딩 중...")
            df = self._load_file(input_path)
            total_rows = len(df)
            self.update_progress(10, f"📂 {total_rows:,}건 로드 완료")

            if self.cancel_flag:
                self.finish_classification(cancelled=True)
                return

            # 2. 텍스트 컬럼 탐지
            primary_col, secondary_col = detect_text_columns(df)
            if primary_col is None:
                raise ValueError("텍스트 컬럼을 찾을 수 없습니다.")

            col_desc = primary_col if secondary_col is None else f"{secondary_col} + {primary_col}"
            self.update_progress(15, f"📝 '{col_desc}' 컬럼 분류 시작...")

            # 3. 분류 실행
            results = []
            for i, (_, row) in enumerate(df.iterrows()):
                if self.cancel_flag:
                    self.finish_classification(cancelled=True)
                    return

                text = compose_text(row, primary_col, secondary_col)
                results.append(self.classifier.predict_single(text))

                if i % max(1, total_rows // 50) == 0:
                    pct = 15 + (i / total_rows) * 72
                    self.update_progress(pct, f"🔄 분류 중... ({i+1:,}/{total_rows:,}건)")

            if self.cancel_flag:
                self.finish_classification(cancelled=True)
                return

            # 4. 결과 열 추가
            self.update_progress(89, "📊 결과 정리 중...")
            df['대분류_자동']    = [r['대분류']      for r in results]
            df['세부분류_자동']  = [r['세부분류']    for r in results]
            df['수요유형']       = [r['수요유형']    for r in results]
            df['수요세부분류']   = [r['수요세부분류'] for r in results]
            df['분류방식']       = [r['분류방식']    for r in results]

            # 5. CSV 저장
            self.update_progress(93, "💾 CSV 파일 저장 중...")
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = re.sub(r'[\\/*?:"<>|]', '_',
                               os.path.splitext(os.path.basename(input_path))[0])
            output_path = os.path.join(output_folder, f"{base_name}_분류결과_{timestamp}.csv")
            df.to_csv(output_path, index=False, encoding='utf-8-sig')

            if not os.path.exists(output_path):
                raise ValueError("파일 저장에 실패했습니다.")

            self.update_progress(100, f"✅ 완료! {total_rows:,}건 분류됨")
            self.root.after(0, lambda: self.save_path_label.config(text=f"💾 저장 완료: {output_path}"))

            # 통계 집계
            rule_count  = sum(1 for r in results if r['분류방식'] == '규칙기반')
            ml_count    = total_rows - rule_count
            value_count = sum(1 for r in results if r['수요유형'] == '가치수요')
            fail_count  = sum(1 for r in results if r['수요유형'] == '실패수요')
            other_count = total_rows - value_count - fail_count

            # 실패수요 세부 집계 (상위 5개)
            fail_sub_counts: dict = {}
            for r in results:
                if r['수요유형'] == '실패수요':
                    k = r['수요세부분류']
                    fail_sub_counts[k] = fail_sub_counts.get(k, 0) + 1
            top_fail = sorted(fail_sub_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            self.root.after(600, lambda: self.show_completion_message(
                output_path, total_rows, rule_count, ml_count,
                value_count, fail_count, other_count, top_fail))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", f"오류 발생:\n\n{e}"))
            self.update_progress(0, f"❌ 오류: {str(e)[:60]}")
        finally:
            self.root.after(0, self.finish_classification)

    def _load_file(self, path: str) -> pd.DataFrame:
        if path.lower().endswith('.csv'):
            for enc in ('utf-8-sig', 'cp949', 'utf-8', 'euc-kr', 'latin1'):
                try:
                    return pd.read_csv(path, encoding=enc, low_memory=False)
                except Exception:
                    continue
            raise ValueError("CSV 파일을 읽을 수 없습니다. (인코딩 오류)")
        return pd.read_excel(path, engine='openpyxl')

    def show_completion_message(self, output_path, total_rows,
                                rule_count, ml_count,
                                value_count, fail_count, other_count,
                                top_fail):
        def pct(n):
            return f"{n/total_rows*100:.1f}%" if total_rows else "0%"

        top_fail_lines = "\n".join(
            f"    {i+1}. {sub}: {cnt:,}건" for i, (sub, cnt) in enumerate(top_fail)
        ) if top_fail else "    (해당 없음)"

        message = f"""✅ 분류가 완료되었습니다!

📊 전체: {total_rows:,}건
  • 규칙 기반: {rule_count:,}건 ({pct(rule_count)})
  • ML 기반:   {ml_count:,}건 ({pct(ml_count)})

🎯 수요유형 분석:
  🟢 가치수요: {value_count:,}건 ({pct(value_count)})
  🔴 실패수요: {fail_count:,}건 ({pct(fail_count)})
  ⚪ 기타:     {other_count:,}건 ({pct(other_count)})

🔴 실패수요 세부분류 (상위 5):
{top_fail_lines}

💾 저장 위치:
{output_path}

파일을 열어보시겠습니까?"""

        if messagebox.askyesno("분류 완료", message):
            try:
                os.startfile(output_path)
            except Exception:
                messagebox.showinfo("알림", f"파일 경로:\n{output_path}")

    def finish_classification(self, cancelled=False):
        self.start_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        if cancelled:
            self.update_progress(0, "❌ 취소되었습니다.")


# ──────────────────────────────────────────────────────────────
# 7. 진입점
# ──────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    QNAClassifierApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
