'use client';

import * as React from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Lightbulb, TrendingUp, Percent, Wallet, Search, Home, Banknote, Map, Users } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import { Spinner } from '@/components/ui/spinner';
import { analyzeRealEstate, type RealEstateAnalysisOutput } from '@/ai/flows/analyze-real-estate-flow';

type Results = {
  jeonseRatio: number;
  ltv: number;
  netYield: number;
};

export default function RealEstatePage() {
  // State for AI Analyzer
  const [addressQuery, setAddressQuery] = React.useState('');
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [analysisResult, setAnalysisResult] = React.useState<RealEstateAnalysisOutput | null>(null);
  const [analysisError, setAnalysisError] = React.useState('');

  // State for existing calculator
  const [propertyPrice, setPropertyPrice] = React.useState('');
  const [deposit, setDeposit] = React.useState('');
  const [monthlyRent, setMonthlyRent] = React.useState('0');
  const [loanAmount, setLoanAmount] = React.useState('');
  const [loanRate, setLoanRate] = React.useState('');
  const [results, setResults] = React.useState<Results | null>(null);
  const [aiComment, setAiComment] = React.useState('');
  const [error, setError] = React.useState('');

  const handleAnalyzeAddress = async () => {
    if (!addressQuery.trim()) {
      setAnalysisError('분석할 아파트 이름이나 주소를 입력해주세요.');
      return;
    }
    setAnalysisError('');
    setAnalysisResult(null);
    setIsAnalyzing(true);
    try {
      const result = await analyzeRealEstate(addressQuery);
      setAnalysisResult(result);
    } catch (e) {
      console.error(e);
      setAnalysisError('AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleCalculate = () => {
    setError('');
    setResults(null);
    setAiComment('');

    const price = parseFloat(propertyPrice);
    const dep = parseFloat(deposit);
    const rent = parseFloat(monthlyRent);
    const loan = parseFloat(loanAmount);
    const rate = parseFloat(loanRate);

    if (isNaN(price) || isNaN(dep) || isNaN(rent) || isNaN(loan) || isNaN(rate)) {
      setError('모든 입력 필드에 유효한 숫자를 입력해주세요.');
      return;
    }

    if (price <= 0) {
      setError('매매가는 0보다 커야 합니다.');
      return;
    }

    const jeonseRatio = (dep / price) * 100;
    const ltv = (loan / price) * 100;

    const annualRent = rent * 12;
    const annualInterest = loan * (rate / 100);
    const investment = price - loan - dep;

    let netYield = 0;
    if (investment > 0) {
      netYield = ((annualRent - annualInterest) / investment) * 100;
    } else {
       // If investment is zero or negative, yield is not meaningfully calculable in percentage.
       // We can represent cash flow directly. For now, we'll show infinity or a message.
       netYield = Infinity;
    }

    setResults({
      jeonseRatio,
      ltv,
      netYield,
    });
    
    // AI Judgment
    if (ltv > 70) {
      setAiComment("LTV(담보인정비율)가 70%를 초과하여 위험도가 매우 높습니다. 대출 규모를 재검토하는 것이 시급합니다.");
    } else if (jeonseRatio > 80) {
      setAiComment("전세가율이 80%를 초과하여 역전세 리스크가 높습니다. 향후 전세가 하락 시 보증금 반환에 어려움이 있을 수 있습니다.");
    } else if (ltv <= 50 && jeonseRatio >= 60 && jeonseRatio <= 75) {
      setAiComment("LTV가 50% 이하로 안정적이며, 전세가율도 60-75% 사이의 적정 구간에 있어 투자 안전성이 비교적 높은 편입니다.");
    } else if (ltv <= 50) {
      setAiComment("LTV가 50% 이하로 안정적입니다. 다만, 전세가율과 임대수익률을 함께 고려하여 최종 투자 결정을 내리는 것이 좋습니다.");
    } else {
      setAiComment("현재 지표만으로는 투자 판단이 복합적입니다. 잠재적 리스크와 기대 수익을 면밀히 분석하고 시장 상황을 추가로 고려하여 신중하게 결정해야 합니다.");
    }
  };

  const formatPercent = (value: number) => {
    if (!isFinite(value)) return "N/A";
    return `${value.toFixed(2)}%`;
  }

  return (
    <div className="p-4 md:p-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">부동산 투자 분석</h1>
        <p className="text-muted-foreground">AI로 신규 투자 타당성을 간편하게 분석하세요.</p>
      </header>

      {/* AI Analyzer Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search />
            AI 기반 주소 검색 분석기
          </CardTitle>
          <CardDescription>분석하고 싶은 아파트 이름이나 주소를 입력하세요.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-2">
            <Input
              id="addressQuery"
              placeholder="예: 반포자이, 서울시 강남구 역삼동 123"
              value={addressQuery}
              onChange={(e) => setAddressQuery(e.target.value)}
              disabled={isAnalyzing}
            />
            <Button onClick={handleAnalyzeAddress} disabled={isAnalyzing} className="sm:w-auto w-full">
              {isAnalyzing ? <Spinner className="mr-2 h-4 w-4" /> : <Lightbulb className="mr-2 h-4 w-4" />}
              AI 지역 분석하기
            </Button>
          </div>
        </CardContent>
      </Card>
      
      {isAnalyzing && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed p-8 text-center">
            <Spinner className="h-8 w-8 text-primary" />
            <p className="text-muted-foreground">AI가 수만 건의 부동산 데이터를 분석하고 있습니다...</p>
        </div>
      )}

      {analysisError && (
        <Alert variant="destructive">
          <AlertTitle>분석 오류</AlertTitle>
          <AlertDescription>{analysisError}</AlertDescription>
        </Alert>
      )}

      {analysisResult && (
        <div className="space-y-6">
          <h2 className="text-2xl font-bold tracking-tight">{addressQuery} 분석 결과</h2>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2"><Home /> 현재 시세</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-bold">매매: {analysisResult.marketPrice.sale}</div>
                <p className="text-xs text-muted-foreground">전세: {analysisResult.marketPrice.jeonse}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2"><Banknote /> 최소 보유 현금</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-bold">{analysisResult.minCash.amount}</div>
                <p className="text-xs text-muted-foreground">{analysisResult.minCash.description}</p>
              </CardContent>
            </Card>
            <Card className="md:col-span-2 lg:col-span-1">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2"><Map /> 주변 상권 및 인프라</CardTitle>
              </CardHeader>
              <CardContent className="text-xs space-y-1 text-muted-foreground">
                <p><span className="font-semibold text-foreground">교통:</span> {analysisResult.infrastructure.transportation}</p>
                <p><span className="font-semibold text-foreground">쇼핑:</span> {analysisResult.infrastructure.shopping}</p>
                <p><span className="font-semibold text-foreground">교육:</span> {analysisResult.infrastructure.education}</p>
                <p><span className="font-semibold text-foreground">기타:</span> {analysisResult.infrastructure.amenities}</p>
              </CardContent>
            </Card>
            <Card className="lg:col-span-2">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2"><TrendingUp /> 향후 전망</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm font-semibold">{analysisResult.prospects.development}</p>
                <p className="text-xs text-muted-foreground mt-1">{analysisResult.prospects.general}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2"><Users /> 거주자 특징</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm font-semibold">주 연령대: {analysisResult.residents.ageGroup}</div>
                <p className="text-xs text-muted-foreground">가족 형태: {analysisResult.residents.familyType}</p>
                <p className="text-xs text-muted-foreground mt-2">{analysisResult.residents.summary}</p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
      
      <Separator className="my-8" />

      {/* Existing Calculator Section */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>수동 투자 분석기</CardTitle>
            <CardDescription>직접 정보를 입력하여 분석합니다.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="propertyPrice">매매가 (원)</Label>
              <Input id="propertyPrice" type="number" placeholder="예: 1000000000" value={propertyPrice} onChange={(e) => setPropertyPrice(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="deposit">보증금 / 전세 (원)</Label>
              <Input id="deposit" type="number" placeholder="예: 500000000" value={deposit} onChange={(e) => setDeposit(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="monthlyRent">월세 (원)</Label>
              <Input id="monthlyRent" type="number" placeholder="전세의 경우 0 입력" value={monthlyRent} onChange={(e) => setMonthlyRent(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="loanAmount">대출 예상 금액 (원)</Label>
              <Input id="loanAmount" type="number" placeholder="예: 400000000" value={loanAmount} onChange={(e) => setLoanAmount(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="loanRate">대출 금리 (연, %)</Label>
              <Input id="loanRate" type="number" placeholder="예: 4.5" value={loanRate} onChange={(e) => setLoanRate(e.target.value)} />
            </div>
          </CardContent>
          <CardFooter>
            <Button onClick={handleCalculate} className="w-full">계산하기</Button>
          </CardFooter>
        </Card>

        {error && (
            <Alert variant="destructive" className="lg:col-span-2">
                <AlertTitle>오류</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
            </Alert>
        )}

        {results && (
            <div className="lg:col-span-2 space-y-6">
                <Card>
                    <CardHeader>
                        <CardTitle>핵심 투자 지표</CardTitle>
                    </CardHeader>
                    <CardContent className="grid gap-4 sm:grid-cols-3">
                        <div className="flex flex-col space-y-1.5 rounded-lg bg-muted/50 p-4">
                            <Label className="text-sm text-muted-foreground flex items-center gap-1"><Percent /> 전세가율</Label>
                            <div className="text-2xl font-bold">{formatPercent(results.jeonseRatio)}</div>
                        </div>
                        <div className="flex flex-col space-y-1.5 rounded-lg bg-muted/50 p-4">
                            <Label className="text-sm text-muted-foreground flex items-center gap-1"><Wallet /> LTV (담보인정비율)</Label>
                            <div className="text-2xl font-bold">{formatPercent(results.ltv)}</div>
                        </div>
                        <div className="flex flex-col space-y-1.5 rounded-lg bg-muted/50 p-4">
                            <Label className="text-sm text-muted-foreground flex items-center gap-1"><TrendingUp /> 순임대수익률</Label>
                            <div className="text-2xl font-bold">{formatPercent(results.netYield)}</div>
                        </div>
                    </CardContent>
                </Card>

                {aiComment && (
                    <Card className="bg-primary/10 border-primary/20">
                         <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-primary/90">
                                <Lightbulb /> AI 투자 판단
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <p className="text-primary/90">{aiComment}</p>
                        </CardContent>
                    </Card>
                )}
            </div>
        )}
      </div>
    </div>
  );
}
