'use server';
/**
 * @fileOverview A real estate analysis AI agent.
 *
 * - analyzeRealEstate - A function that handles the real estate analysis process.
 * - RealEstateAnalysisInput - The input type for the analyzeRealestate function.
 * - RealEstateAnalysisOutput - The return type for the analyzeRealestate function.
 */

import { ai } from '@/ai/genkit';
import { z } from 'zod';

const RealEstateAnalysisInputSchema = z.string().describe("The address or name of the apartment to analyze.");
export type RealEstateAnalysisInput = z.infer<typeof RealEstateAnalysisInputSchema>;

const RealEstateAnalysisOutputSchema = z.object({
  marketPrice: z.object({
    sale: z.string().describe("예상 매매가 (원 단위, 범위로 표시 가능 예: 10억 ~ 11억)"),
    jeonse: z.string().describe("예상 전세가 (원 단위, 범위로 표시 가능 예: 7억 ~ 7.5억)"),
  }).describe("현재 시세"),
  minCash: z.object({
    amount: z.string().describe("필요한 최소 현금 (원 단위)"),
    description: z.string().describe("계산 근거 설명 (예: 매매가 10억, LTV 50% 적용 시...)"),
  }).describe("최소 보유 현금"),
  infrastructure: z.object({
    transportation: z.string().describe("지하철, 버스 등 대중교통 접근성"),
    shopping: z.string().describe("마트, 백화점, 시장 등 쇼핑 시설"),
    education: z.string().describe("주요 학군, 학교, 학원가 정보"),
    amenities: z.string().describe("병원, 공원, 관공서 등 기타 편의시설"),
  }).describe("주변 상권 및 인프라"),
  prospects: z.object({
    development: z.string().describe("교통 호재(GTX, 신규 노선), 재건축/재개발 가능성 등"),
    general: z.string().describe("지역 가치에 대한 종합적인 향후 전망"),
  }).describe("향후 전망"),
  residents: z.object({
    ageGroup: z.string().describe("주 거주 연령대"),
    familyType: z.string().describe("주요 가족 형태 (예: 1인 가구, 신혼부부, 자녀가 있는 3-4인 가구)"),
    summary: z.string().describe("거주자 특징에 대한 종합적인 요약"),
  }).describe("거주자 특징"),
});

export type RealEstateAnalysisOutput = z.infer<typeof RealEstateAnalysisOutputSchema>;

const analysisPrompt = ai.definePrompt(
  {
    name: 'realEstateAnalysisPrompt',
    input: { schema: z.object({ address: z.string() }) },
    output: { schema: RealEstateAnalysisOutputSchema },
    prompt: `You are an expert real estate analyst in Korea.
Analyze the property at the following address: "{{{address}}}".

Provide a detailed analysis based on the following 5 categories.
Your response MUST be a JSON object that conforms to the output schema.
Provide all monetary values in Korean Won (KRW). Be specific and use realistic data based on recent market trends.

1.  **현재 시세 (Current Market Price)**: Estimate the current sale price and "jeonse" price.
2.  **최소 보유 현금 (Minimum Cash Needed)**: Calculate the minimum cash required to purchase, assuming a loan-to-value (LTV) ratio of 50-60%. Explain the calculation.
3.  **주변 상권 및 인프라 (Surrounding Commercial Area & Infrastructure)**: Describe nearby subways, major marts/malls, hospitals, and the quality of the school district (hakgun).
4.  **향후 전망 (Future Prospects)**: Analyze future potential based on transportation developments (like GTX), redevelopment/reconstruction possibilities, and other regional value drivers.
5.  **거주자 특징 (Resident Characteristics)**: Describe the primary resident demographic, including main age groups and family types (e.g., dual-income couples, families with children).

Do not include any text outside of the JSON object.`,
    config: {
        temperature: 0.3,
        model: 'gemini-1.5-pro-latest'
    }
  }
);

const analyzeRealEstateFlow = ai.defineFlow(
  {
    name: 'analyzeRealEstateFlow',
    inputSchema: RealEstateAnalysisInputSchema,
    outputSchema: RealEstateAnalysisOutputSchema,
  },
  async (address) => {
    const { output } = await analysisPrompt({ address: address });
    if (!output) {
        throw new Error("AI analysis failed to produce an output.");
    }
    return output;
  }
);

export async function analyzeRealEstate(input: RealEstateAnalysisInput): Promise<RealEstateAnalysisOutput> {
  return analyzeRealEstateFlow(input);
}
