export interface Asset {
  category: string;
  items: {
    name: string;
    amount: number;
  }[];
}

export interface Liability {
  name: string;
  amount: number;
}

export interface Expense {
    category: '필수 지출' | '선택적 지출' | '저축 및 투자';
    amount: number;
    icon: React.ComponentType<{ className?: string }>;
}

export interface BudgetItem extends Expense {
    fill: string;
}
