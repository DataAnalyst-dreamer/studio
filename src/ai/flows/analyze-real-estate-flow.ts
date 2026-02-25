'use server';
/**
 * @fileOverview A real estate analysis AI agent.
 *
 * - analyzeRealEstate - A function that handles the real estate analysis process.
 * - RealEstateAnalysisInput - The input type for the analyzeRealEstate function.
 * - RealEstateAnalysisOutput - The return type for the analyzeRealEstate function.
 */

import { ai } from '@/ai/genkit';
import { z } from 'zod';

const PriceHistoryItemSchema = z.object({
  period: z.string().describe("기간 레이블 (예: '22.1Q', '22.2Q', ..., '24.4Q' 형식)"),
  sale: z.number().describe("해당 분기 매매가 중앙값 (억 원 단위 숫자, 예: 9.5)"),
  jeonse: z.number().describe("해당 분기 전세가 중앙값 (억 원 단위 숫자, 예: 6.2)"),
});
export type PriceHistoryItem = z.infer<typeof PriceHistoryItemSchema>;

const RealEstateAnalysisInputSchema = z.string().describe("분석할 부동산 주소 또는 아파트명");
export type RealEstateAnalysisInput = z.infer<typeof RealEstateAnalysisInputSchema>;

const RealEstateAnalysisOutputSchema = z.object({
  // ── 메타 정보 ──────────────────────────────────────────────────────
  isSimulation: z
    .boolean()
    .describe(
      "정확한 실거래 DB 데이터가 없어 AI 추정 시뮬레이션으로 생성된 경우 true, 실제 데이터 기반이면 false"
    ),
  dataSource: z
    .string()
    .describe(
      "데이터 출처 설명 (예: '국토부 실거래가 기반 AI 추정치' 또는 'AI 시뮬레이션 - 안양시 신축 아파트 평균 시세 기반 추정치')"
    ),

  // ── 차트용 숫자 필드 ────────────────────────────────────────────────
  salePrice: z.number().describe("현재 매매가 대표값 (억 원 단위 숫자, 예: 10.5)"),
  jeonsePrice: z.number().describe("현재 전세가 대표값 (억 원 단위 숫자, 예: 7.0)"),
  jeonseRatioNum: z.number().describe("전세가율 (%, 0-100 사이 숫자, 예: 66.7)"),
  ltvNum: z.number().describe("적용 가능 LTV (%, 0-100 사이 숫자, 예: 50)"),
  rentalYieldNum: z.number().describe("연간 임대수익률 (%, 0-15 사이 숫자, 예: 3.2)"),
  minCashNum: z.number().describe("취득세 포함 최소 필요 현금 (억 원 단위 숫자, 예: 5.2)"),
  livabilityScoreNum: z.number().describe("종합 입지 점수 (10점 만점, 숫자, 예: 7.5)"),

  // ── 시계열 데이터 ──────────────────────────────────────────────────
  priceHistory: z
    .array(PriceHistoryItemSchema)
    .length(12)
    .describe(
      "최근 3년간 분기별 시세 추이. 반드시 12개 항목. " +
      "period 형식: '22.1Q', '22.2Q', '22.3Q', '22.4Q', '23.1Q', ..., '24.4Q'"
    ),

  // ── 텍스트 분석 필드 ────────────────────────────────────────────────
  marketPrice: z
    .object({
      sale: z.string().describe("예상 매매가 텍스트 (예: '10억 ~ 11억 원')"),
      jeonse: z.string().describe("예상 전세가 텍스트 (예: '7억 ~ 7.5억 원')"),
      jeonseRatio: z.string().describe("전세가율 및 갭투자 위험도 평가 텍스트"),
    })
    .describe("현재 시세"),

  investmentFeasibility: z
    .object({
      rentalYield: z.string().describe("연간 임대수익률 설명"),
      ltv: z.string().describe("LTV 규제 및 대출 한도 설명"),
      dsr: z.string().describe("DSR 기준 적정 소득 요건 설명"),
      minCashRequired: z.string().describe("취득세 포함 최소 현금 상세 설명"),
      breakEvenAnalysis: z.string().describe("손익분기점 분석 - 보유 기간 및 수익 실현 조건"),
    })
    .describe("투자 타당성 분석"),

  riskAssessment: z
    .object({
      marketRisk: z.string().describe("시장 리스크 설명"),
      regulatoryRisk: z.string().describe("규제 리스크 설명"),
      interestRateRisk: z.string().describe("금리 리스크 설명"),
      overallRisk: z
        .enum(['낮음', '보통', '높음'])
        .describe("종합 리스크 등급 (낮음/보통/높음 중 하나만)"),
    })
    .describe("리스크 분석"),

  locationAnalysis: z
    .object({
      transportation: z.string().describe("대중교통 접근성"),
      education: z.string().describe("학군 및 교육 환경"),
      shopping: z.string().describe("쇼핑 및 생활 편의"),
      amenities: z.string().describe("의료·공원·관공서 등 편의시설"),
      livabilityScore: z.string().describe("종합 입지 점수 및 평가 (예: '7.5/10 - 교통 우수')"),
    })
    .describe("입지 분석"),

  futureProspects: z
    .object({
      developmentPlan: z.string().describe("교통 호재·재건축·개발 계획"),
      populationTrend: z.string().describe("인구 유입·유출 추이"),
      policyImpact: z.string().describe("정부 정책 영향도"),
      investmentOutlook: z.string().describe("3~5년 중장기 투자 전망"),
    })
    .describe("미래 가치 분석"),

  residents: z
    .object({
      ageGroup: z.string().describe("주 거주 연령대"),
      familyType: z.string().describe("주요 가족 형태"),
      summary: z.string().describe("거주자 특징 요약"),
    })
    .describe("거주자 특징"),

  overallConclusion: z
    .object({
      investmentGrade: z
        .enum(['A', 'B', 'C', 'D'])
        .describe("투자 등급 (A/B/C/D 중 하나만)"),
      strengths: z.array(z.string()).length(3).describe("핵심 장점 3가지 (문자열 배열)"),
      weaknesses: z.array(z.string()).length(3).describe("핵심 주의사항 3가지 (문자열 배열)"),
      recommendation: z
        .enum(['매수 적극', '매수 검토', '관망', '매수 보류'])
        .describe("최종 투자 추천 (4가지 중 하나만)"),
    })
    .describe("종합 투자 결론"),
});

export type RealEstateAnalysisOutput = z.infer<typeof RealEstateAnalysisOutputSchema>;

const SYSTEM_PROMPT = `당신은 대한민국 최고의 부동산 타당성 분석 전문가입니다.
아래는 자산관리 가이드 Section 9 (부동산 타당성 분석)의 핵심 분석 기준입니다.

[할루시네이션 방지 원칙 - 최우선 준수 사항]

특정 아파트(예: 안양시 아르테자이)의 정확한 실거래가 DB를 확실히 알고 있는 경우에만 실제 수치를 사용하십시오.
정확한 데이터를 확신할 수 없는 경우에는 다음 지침을 따르십시오:
  1. isSimulation = true 로 설정하십시오.
  2. dataSource = "AI 시뮬레이션 - [해당 시/구] 유사 신축 아파트 평균 시세 기반 추정치" 로 설정하십시오.
  3. 해당 주소가 위치한 지역(시/구/동)의 평균적인 신규 분양/입주 아파트 시세를 기준으로 현실적인 시뮬레이션 데이터를 생성하십시오.
  4. 실제 데이터인 척 단정적으로 서술하지 말고, 추정임을 맥락에서 알 수 있게 하십시오.
정확한 데이터를 확신할 수 있는 경우: isSimulation = false, dataSource = "국토부 실거래가 기반 AI 추정치"

[Section 9 부동산 타당성 분석 기준]

§9.1 시장 분석
- 전세가율 = (전세가 / 매매가) × 100
- 전세가율 70% 이상: 갭투자 위험 높음 / 50~70%: 보통 / 50% 미만: 안전

§9.2 수익성 분석
- 임대수익률 = (연간 임대수입 / 매매가) × 100
- LTV: 투기과열지구 40~50%, 조정대상지역 50~60%, 비규제지역 70%
- DSR 40% 기준 역산
- 취득세(1~3%, 다주택 최대 12%) + 중개수수료(0.4~0.9%) + 수리비 포함 최소 현금 산출

§9.3 리스크 분석
- 시장/규제/금리 리스크를 개별 분석 후 종합 등급 산출 (낮음/보통/높음)

§9.4 입지 분석
- 교통(3) + 교육(3) + 편의시설(2) + 환경(2) = 10점 만점

§9.5 미래 가치
- GTX/신규 지하철, 재건축 연한·조합 현황, 인구 동향, 정책 영향도

§9.6 종합 결론
- A등급: 리스크↓ 수익성↑ 입지↑ → 매수 적극
- B등급: 리스크 보통 수익성 양호 → 매수 검토
- C등급: 리스크 보통~높음 수익성↓ → 관망
- D등급: 리스크↑ 수익성↓↓ → 매수 보류

[시계열 데이터 생성 규칙]
priceHistory 배열은 반드시 12개 항목이어야 합니다.
period 값: '22.1Q', '22.2Q', '22.3Q', '22.4Q', '23.1Q', '23.2Q', '23.3Q', '23.4Q', '24.1Q', '24.2Q', '24.3Q', '24.4Q'
sale과 jeonse는 반드시 억 원 단위의 숫자(float)여야 합니다.
실제 시장 흐름(2022년 하락, 2023년 저점, 2024년 회복)을 반영하십시오.

[응답 규칙]
- 응답은 반드시 주어진 JSON 스키마를 정확히 따르십시오.
- JSON 외 다른 텍스트는 절대 포함하지 마십시오.
- 모든 설명은 한국어로 작성하십시오.`;

const analysisPrompt = ai.definePrompt(
  {
    name: 'realEstateAnalysisPrompt',
    input: { schema: z.object({ address: z.string() }) },
    output: { schema: RealEstateAnalysisOutputSchema },
    system: SYSTEM_PROMPT,
    prompt: `다음 부동산에 대해 자산관리 가이드 Section 9 기준에 따라 타당성 분석을 수행하십시오.

분석 대상: {{{address}}}

반드시 포함해야 할 항목:
- isSimulation (bool): 정확한 데이터 여부
- dataSource (string): 데이터 출처
- salePrice, jeonsePrice (number, 억 원): 차트용 현재 시세
- jeonseRatioNum, ltvNum, rentalYieldNum, minCashNum, livabilityScoreNum (number): 차트용 지표
- priceHistory (array, 12개): 2022년 1분기 ~ 2024년 4분기 분기별 시세
- marketPrice, investmentFeasibility, riskAssessment, locationAnalysis, futureProspects, residents, overallConclusion: 텍스트 상세 분석`,
    model: 'googleai/gemini-2.5-flash',
    config: {
      temperature: 0.3,
    },
  }
);

const analyzeRealEstateFlow = ai.defineFlow(
  {
    name: 'analyzeRealEstateFlow',
    inputSchema: RealEstateAnalysisInputSchema,
    outputSchema: RealEstateAnalysisOutputSchema,
  },
  async (address) => {
    const { output } = await analysisPrompt({ address });
    if (!output) {
      throw new Error('AI 분석 결과를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.');
    }
    return output;
  }
);

export async function analyzeRealEstate(
  input: RealEstateAnalysisInput
): Promise<RealEstateAnalysisOutput> {
  return analyzeRealEstateFlow(input);
}
