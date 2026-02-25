import { Wallet, Landmark, TrendingUp, CreditCard, School, CircleDollarSign, ShieldCheck, Car, Building, Gem, PiggyBank, HandCoins, Repeat } from 'lucide-react';
import type { Asset, Liability, BudgetItem } from './types';

export const assets: Asset[] = [
  {
    category: "유동자산",
    items: [
      { name: "현금 및 요구불예금", amount: 15000000 },
      { name: "단기 적금 / CMA / MMF", amount: 35000000 },
      { name: "비상금", amount: 20000000 },
    ],
  },
  {
    category: "투자자산",
    items: [
      { name: "국내외 주식 / ETF", amount: 120000000 },
      { name: "채권 / 채권형 펀드", amount: 50000000 },
      { name: "가상자산", amount: 8000000 },
      { name: "연금 계좌 (IRP/연금저축)", amount: 45000000 },
    ],
  },
  {
    category: "실물자산",
    items: [
      { name: "부동산", amount: 650000000 },
      { name: "자동차", amount: 25000000 },
      { name: "금 / 원자재", amount: 12000000 },
    ],
  },
];

export const liabilities: Liability[] = [
    { name: '주택담보대출', amount: 300000000 },
    { name: '신용대출 / 카드론', amount: 20000000 },
    { name: '학자금 대출', amount: 15000000 },
];

export const totalIncome = 6000000;

export const expenses: { category: '고정지출' | '변동지출', items: { name: string, amount: number }[] }[] = [
    {
        category: '고정지출',
        items: [
            { name: '주거비', amount: 1200000 },
            { name: '보험료', amount: 150000 },
            { name: '구독 서비스', amount: 50000 },
            { name: '대출 상환', amount: 1600000 },
        ]
    },
    {
        category: '변동지출',
        items: [
            { name: '식비', amount: 600000 },
            { name: '교통비', amount: 150000 },
            { name: '의류', amount: 200000 },
            { name: '여가', amount: 300000 },
        ]
    }
];

export const savings = {
    name: '저축·투자',
    amount: totalIncome - expenses.reduce((acc, cat) => acc + cat.items.reduce((itemAcc, item) => itemAcc + item.amount, 0), 0)
};

const essentialSpending = expenses[0].items.reduce((sum, item) => sum + item.amount, 0);
const discretionarySpending = expenses[1].items.reduce((sum, item) => sum + item.amount, 0);

export const budgetData: BudgetItem[] = [
    {
        category: '필수 지출',
        amount: essentialSpending,
        icon: Wallet,
        fill: 'hsl(var(--chart-1))',
    },
    {
        category: '선택적 지출',
        amount: discretionarySpending,
        icon: HandCoins,
        fill: 'hsl(var(--chart-2))',
    },
    {
        category: '저축 및 투자',
        amount: savings.amount,
        icon: PiggyBank,
        fill: 'hsl(var(--chart-3))',
    },
];

export const totalAssets = assets.reduce((total, category) => total + category.items.reduce((catTotal, item) => catTotal + item.amount, 0), 0);
export const totalLiabilities = liabilities.reduce((total, liability) => total + liability.amount, 0);
export const netWorth = totalAssets - totalLiabilities;
