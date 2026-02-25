export const formatCurrency = (value: number) => {
  if (typeof value !== 'number') return '';
  return new Intl.NumberFormat('ko-KR', {
    style: 'currency',
    currency: 'KRW',
  }).format(value);
};
