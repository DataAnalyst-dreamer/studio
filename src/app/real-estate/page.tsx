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
import { Lightbulb, TrendingUp, Percent, Wallet } from 'lucide-react';

type Results = {
  jeonseRatio: number;
  ltv: number;
  netYield: number;
};

export default function RealEstatePage() {
  const [propertyPrice, setPropertyPrice] = React.useState('');
  const [deposit, setDeposit] = React.useState('');
  const [monthlyRent, setMonthlyRent] = React.useState('0');
  const [loanAmount, setLoanAmount] = React.useState('');
  const [loanRate, setLoanRate] = React.useState('');

  const [results, setResults] = React.useState<Results | null>(null);
  const [aiComment, setAiComment] = React.useState('');
  const [error, setError] = React.useState('');

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
        <p className="text-muted-foreground">신규 투자 타당성을 간편하게 분석하세요.</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>투자 정보 입력</CardTitle>
            <CardDescription>분석에 필요한 정보를 입력하세요.</CardDescription>
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
