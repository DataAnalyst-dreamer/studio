'use client';

import * as React from 'react';
import {
  Landmark,
  TrendingUp,
  TrendingDown,
  Wallet,
  PiggyBank,
  HandCoins,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import {
  RadialBar,
  RadialBarChart,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  assets,
  liabilities,
  netWorth,
  totalAssets,
  totalLiabilities,
  budgetData,
  expenses,
  savings,
  totalIncome,
} from '@/lib/dashboard-data';
import type { BudgetItem } from '@/lib/types';

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
  }).format(value);
};

export default function DashboardPage() {
  const totalOutgoing = expenses.reduce((acc, cat) => acc + cat.items.reduce((itemAcc, item) => itemAcc + item.amount, 0), 0) + savings.amount;

  return (
    <div className="p-4 md:p-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">자산 관리 대시보드</h1>
        <p className="text-muted-foreground">자산 현황과 현금 흐름을 한눈에 파악하세요.</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Landmark />
              자산 현황 (Net Worth)
            </CardTitle>
            <CardDescription>순자산 = 총자산 - 총부채</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-3">
            <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-4">
              <div className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                <ArrowUpRight className="h-4 w-4 text-green-500" />
                총 자산
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(totalAssets)}
              </div>
            </div>
             <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-4">
              <div className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                <ArrowDownRight className="h-4 w-4 text-red-500" />
                총 부채
              </div>
              <div className="text-2xl font-bold">
                {formatCurrency(totalLiabilities)}
              </div>
            </div>
             <div className="flex flex-col gap-1 rounded-lg bg-primary/10 p-4">
              <div className="text-sm font-medium text-primary/80">순 자산</div>
              <div className="text-2xl font-bold text-primary">
                {formatCurrency(netWorth)}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1 flex flex-col">
           <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp />
              50-30-20 예산 규칙
            </CardTitle>
            <CardDescription>월별 지출 및 저축 현황</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex items-center justify-center">
            <ChartContainer
              config={{}}
              className="mx-auto aspect-square w-full max-w-[250px]"
            >
              <ResponsiveContainer width="100%" height="100%">
                 <RadialBarChart
                    data={budgetData}
                    innerRadius="30%"
                    outerRadius="100%"
                    startAngle={90}
                    endAngle={-270}
                    barSize={20}
                  >
                    <ChartTooltip
                      cursor={false}
                      content={<ChartTooltipContent hideLabel />}
                    />
                    <RadialBar dataKey="amount" background cornerRadius={5} />
                    <Legend
                      content={({ payload }) => (
                         <ul className="flex flex-col gap-2 mt-4 text-sm">
                          {payload?.map((entry) => {
                             const item = budgetData.find(d => d.category === entry.payload?.payload.category)!;
                             const percentage = ((item.amount / totalOutgoing) * 100).toFixed(1);
                             const Icon = item.icon;
                            return (
                              <li key={item.category} className="flex items-center gap-2">
                                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.fill }} />
                                <span className="text-muted-foreground">{item.category}</span>
                                <span className="font-semibold ml-auto">{formatCurrency(item.amount)}</span>
                                <span className="w-12 text-right font-mono text-muted-foreground">{percentage}%</span>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    />
                  </RadialBarChart>
              </ResponsiveContainer>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>자산 상세</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
             {assets.map((assetCat) => (
                <div key={assetCat.category}>
                    <h3 className="text-sm font-medium text-muted-foreground mb-2">{assetCat.category}</h3>
                    <div className="space-y-2">
                    {assetCat.items.map((item) => (
                        <div key={item.name} className="flex justify-between items-center text-sm p-2 rounded-md hover:bg-muted/50">
                            <span>{item.name}</span>
                            <span className="font-mono">{formatCurrency(item.amount)}</span>
                        </div>
                    ))}
                    </div>
                </div>
             ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>현금흐름 관리</CardTitle>
            <CardDescription>월간 수입 및 지출 내역</CardDescription>
          </CardHeader>
          <CardContent className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold mb-2">월 수입</h3>
              <div className="flex justify-between items-center p-3 bg-muted/50 rounded-lg">
                <span className="text-sm">총 수입</span>
                <span className="text-lg font-bold text-green-400">{formatCurrency(totalIncome)}</span>
              </div>
            </div>
            <div className="space-y-4">
              <h3 className="font-semibold">월 지출 및 저축</h3>
               {expenses.map((expenseCat) => (
                <div key={expenseCat.category}>
                    <h4 className="text-sm font-medium text-muted-foreground mb-2">{expenseCat.category}</h4>
                    <div className="space-y-1">
                    {expenseCat.items.map((item) => (
                        <div key={item.name} className="flex justify-between items-center text-sm p-2">
                            <span>{item.name}</span>
                            <span className="font-mono">{formatCurrency(item.amount)}</span>
                        </div>
                    ))}
                    </div>
                </div>
             ))}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">저축 및 투자</h4>
                 <div className="flex justify-between items-center text-sm p-2">
                    <span>{savings.name}</span>
                    <span className="font-mono">{formatCurrency(savings.amount)}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
            <CardHeader>
                <CardTitle>부채 상세</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                {liabilities.map((item) => (
                    <div key={item.name} className="flex justify-between items-center text-sm p-2 rounded-md hover:bg-muted/50">
                        <span>{item.name}</span>
                        <span className="font-mono text-red-400">{formatCurrency(item.amount)}</span>
                    </div>
                ))}
                </div>
            </CardContent>
        </Card>
      </div>
    </div>
  );
}
