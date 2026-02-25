'use client';

import * as React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { Spinner } from '@/components/ui/spinner';
import {
  Search,
  TrendingUp,
  ShieldAlert,
  Map,
  Users,
  Lightbulb,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Info,
} from 'lucide-react';
import {
  analyzeRealEstate,
  type RealEstateAnalysisOutput,
} from '@/ai/flows/analyze-real-estate-flow';
import { cn } from '@/lib/utils';

// ── 투자 등급 색상 ─────────────────────────────────────────────────────
const GRADE_CONFIG: Record<string, { bg: string; text: string; border: string; label: string }> = {
  A: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30', label: '매수 적극' },
  B: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30', label: '매수 검토' },
  C: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30', label: '관망' },
  D: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30', label: '매수 보류' },
};

const RISK_CONFIG: Record<string, { color: string; bg: string }> = {
  낮음: { color: '#10b981', bg: 'bg-emerald-500/10' },
  보통: { color: '#f59e0b', bg: 'bg-amber-500/10' },
  높음: { color: '#ef4444', bg: 'bg-red-500/10' },
};

// ── 원형 게이지 컴포넌트 ──────────────────────────────────────────────
function CircularGauge({
  value,
  max,
  label,
  unit = '%',
  color,
  size = 96,
}: {
  value: number;
  max: number;
  label: string;
  unit?: string;
  color: string;
  size?: number;
}) {
  const clamped = Math.min(Math.max(value, 0), max);
  const pct = clamped / max;
  const r = 36;
  const cx = 48;
  const cy = 48;
  const circ = 2 * Math.PI * r;
  const dashOffset = circ * (1 - pct);

  return (
    <div className="flex flex-col items-center gap-1.5">
      <svg width={size} height={size} viewBox="0 0 96 96">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#334155" strokeWidth="8" />
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circ}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
        <text x={cx} y={cy - 4} textAnchor="middle" fontSize="14" fontWeight="700" fill="white">
          {value.toFixed(1)}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" fontSize="9" fill="#94a3b8">
          {unit}
        </text>
      </svg>
      <span className="text-xs text-muted-foreground text-center leading-tight">{label}</span>
    </div>
  );
}

// ── 큰 숫자 카드 ─────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-border/50 bg-card/60 p-4 flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn('text-2xl font-black tracking-tight', accent ?? 'text-foreground')}>{value}</span>
      {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
    </div>
  );
}

// ── 커스텀 툴팁 ───────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card p-3 text-xs shadow-xl">
      <p className="font-semibold mb-1 text-foreground">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <span className="font-bold">{p.value.toFixed(2)}억</span>
        </p>
      ))}
    </div>
  );
}

// ── 메인 페이지 ───────────────────────────────────────────────────────
export default function RealEstatePage() {
  const [query, setQuery] = React.useState('');
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [result, setResult] = React.useState<RealEstateAnalysisOutput | null>(null);
  const [error, setError] = React.useState('');

  const handleAnalyze = async () => {
    if (!query.trim()) {
      setError('분석할 아파트 이름이나 주소를 입력해주세요.');
      return;
    }
    setError('');
    setResult(null);
    setIsAnalyzing(true);
    try {
      const data = await analyzeRealEstate(query);
      setResult(data);
    } catch (e) {
      console.error(e);
      setError('AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleAnalyze();
  };

  const gradeConf = result ? (GRADE_CONFIG[result.overallConclusion.investmentGrade] ?? GRADE_CONFIG['C']) : null;
  const riskConf = result ? (RISK_CONFIG[result.riskAssessment.overallRisk] ?? RISK_CONFIG['보통']) : null;

  return (
    <div className="p-4 md:p-8 space-y-8 max-w-6xl mx-auto">
      {/* ── 헤더 ── */}
      <header>
        <h1 className="text-3xl font-bold tracking-tight">부동산 AI 타당성 분석</h1>
        <p className="text-muted-foreground mt-1">아파트 이름 또는 주소를 입력하면 AI가 투자 타당성을 분석합니다.</p>
      </header>

      {/* ── 검색창 ── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Search className="h-4 w-4" />
            AI 부동산 분석기
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-2">
            <Input
              placeholder="예: 반포자이, 안양시 아르테자이, 서울시 마포구 래미안 웰스트림"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isAnalyzing}
              className="flex-1"
            />
            <Button onClick={handleAnalyze} disabled={isAnalyzing} className="sm:w-auto">
              {isAnalyzing ? (
                <Spinner className="mr-2 h-4 w-4" />
              ) : (
                <Lightbulb className="mr-2 h-4 w-4" />
              )}
              {isAnalyzing ? '분석 중...' : 'AI 분석 시작'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── 로딩 ── */}
      {isAnalyzing && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-primary/30 p-12 text-center">
          <Spinner className="h-10 w-10 text-primary" />
          <div>
            <p className="font-semibold">AI가 분석 중입니다</p>
            <p className="text-sm text-muted-foreground mt-1">
              국토부 실거래가 데이터와 지역 시세를 기반으로 분석하고 있습니다...
            </p>
          </div>
        </div>
      )}

      {/* ── 에러 ── */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>분석 오류</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          분석 결과 대시보드
      ══════════════════════════════════════════════════════════════════ */}
      {result && gradeConf && riskConf && (
        <div className="space-y-6">
          {/* ── 시뮬레이션 뱃지 + 데이터 출처 ── */}
          <div className="flex flex-wrap items-center gap-2">
            {result.isSimulation ? (
              <Badge
                variant="outline"
                className="border-amber-500/60 text-amber-400 bg-amber-500/10 text-sm px-3 py-1 font-semibold"
              >
                ⚠ AI 추정 시뮬레이션 결과
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className="border-emerald-500/60 text-emerald-400 bg-emerald-500/10 text-sm px-3 py-1 font-semibold"
              >
                ✓ 실거래 데이터 기반
              </Badge>
            )}
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Info className="h-3 w-3" />
              {result.dataSource}
            </span>
          </div>

          {/* ── 종합 결론 헤더 카드 ── */}
          <Card className={cn('border', gradeConf.border, gradeConf.bg)}>
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">종합 투자 등급</p>
                  <div className="flex items-baseline gap-3">
                    <span className={cn('text-7xl font-black', gradeConf.text)}>
                      {result.overallConclusion.investmentGrade}
                    </span>
                    <span className={cn('text-xl font-bold', gradeConf.text)}>
                      {result.overallConclusion.recommendation}
                    </span>
                  </div>
                </div>
                <div className="flex flex-col gap-3 flex-1 sm:pl-8 min-w-0">
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-1.5">핵심 장점</p>
                    <ul className="space-y-1">
                      {result.overallConclusion.strengths.map((s, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-xs text-foreground">
                          <CheckCircle2 className="h-3 w-3 text-emerald-400 mt-0.5 shrink-0" />
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-1.5">주의사항</p>
                    <ul className="space-y-1">
                      {result.overallConclusion.weaknesses.map((w, i) => (
                        <li key={i} className="flex items-start gap-1.5 text-xs text-foreground">
                          <XCircle className="h-3 w-3 text-red-400 mt-0.5 shrink-0" />
                          {w}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ── 핵심 시세 지표 ── */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCard
              label="현재 매매가"
              value={`${result.salePrice.toFixed(1)}억`}
              sub={result.marketPrice.sale}
              accent="text-primary"
            />
            <StatCard
              label="현재 전세가"
              value={`${result.jeonsePrice.toFixed(1)}억`}
              sub={result.marketPrice.jeonse}
            />
            <StatCard
              label="최소 보유 현금"
              value={`${result.minCashNum.toFixed(1)}억`}
              sub="취득세 포함"
              accent="text-amber-400"
            />
            <StatCard
              label="임대 수익률"
              value={`${result.rentalYieldNum.toFixed(1)}%`}
              sub="연간 (월세 기준)"
            />
            <StatCard
              label="LTV 한도"
              value={`${result.ltvNum.toFixed(0)}%`}
              sub="지역 규제 반영"
            />
            <StatCard
              label="전세가율"
              value={`${result.jeonseRatioNum.toFixed(1)}%`}
              sub={result.jeonseRatioNum >= 70 ? '⚠ 갭투자 위험' : result.jeonseRatioNum >= 50 ? '보통' : '안전'}
              accent={
                result.jeonseRatioNum >= 70
                  ? 'text-red-400'
                  : result.jeonseRatioNum >= 50
                  ? 'text-amber-400'
                  : 'text-emerald-400'
              }
            />
          </div>

          {/* ── 시계열 차트 ── */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <TrendingUp className="h-4 w-4 text-primary" />
                최근 3년 시세 트렌드 (2022~2024)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={result.priceHistory} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="period"
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    axisLine={{ stroke: '#334155' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => `${v}억`}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: '12px', paddingTop: '12px' }}
                    formatter={(value) => (value === 'sale' ? '매매가 (억)' : '전세가 (억)')}
                  />
                  <Line
                    type="monotone"
                    dataKey="sale"
                    stroke="#818cf8"
                    strokeWidth={2.5}
                    dot={{ r: 3, fill: '#818cf8', strokeWidth: 0 }}
                    activeDot={{ r: 5 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="jeonse"
                    stroke="#34d399"
                    strokeWidth={2.5}
                    dot={{ r: 3, fill: '#34d399', strokeWidth: 0 }}
                    activeDot={{ r: 5 }}
                    strokeDasharray="5 3"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* ── 원형 게이지 3종 ── */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">핵심 투자 지표</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex justify-around flex-wrap gap-6 py-2">
                <CircularGauge
                  value={result.jeonseRatioNum}
                  max={100}
                  label="전세가율"
                  color={result.jeonseRatioNum >= 70 ? '#ef4444' : result.jeonseRatioNum >= 50 ? '#f59e0b' : '#10b981'}
                  size={110}
                />
                <CircularGauge
                  value={result.ltvNum}
                  max={100}
                  label="적용 LTV"
                  color="#818cf8"
                  size={110}
                />
                <CircularGauge
                  value={result.rentalYieldNum}
                  max={10}
                  label="임대수익률"
                  color="#34d399"
                  size={110}
                />
                <CircularGauge
                  value={result.livabilityScoreNum}
                  max={10}
                  label="입지 점수"
                  unit="/10"
                  color="#fb923c"
                  size={110}
                />
              </div>
              <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-muted-foreground text-center">
                <p>{result.investmentFeasibility.ltv}</p>
                <p>{result.marketPrice.jeonseRatio}</p>
                <p>{result.investmentFeasibility.rentalYield}</p>
                <p>{result.locationAnalysis.livabilityScore}</p>
              </div>
            </CardContent>
          </Card>

          {/* ── 리스크 · 입지 · 미래 · 거주자 ── */}
          <div className="grid gap-4 md:grid-cols-2">
            {/* 리스크 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4" />
                    리스크 분석
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      'text-xs',
                      result.riskAssessment.overallRisk === '낮음'
                        ? 'border-emerald-500/60 text-emerald-400'
                        : result.riskAssessment.overallRisk === '보통'
                        ? 'border-amber-500/60 text-amber-400'
                        : 'border-red-500/60 text-red-400'
                    )}
                  >
                    종합: {result.riskAssessment.overallRisk}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs">
                <RiskRow label="시장 리스크" text={result.riskAssessment.marketRisk} />
                <RiskRow label="규제 리스크" text={result.riskAssessment.regulatoryRisk} />
                <RiskRow label="금리 리스크" text={result.riskAssessment.interestRateRisk} />
              </CardContent>
            </Card>

            {/* 입지 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Map className="h-4 w-4" />
                  입지 분석
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs">
                <InfoRow label="교통" text={result.locationAnalysis.transportation} />
                <InfoRow label="교육" text={result.locationAnalysis.education} />
                <InfoRow label="쇼핑" text={result.locationAnalysis.shopping} />
                <InfoRow label="편의시설" text={result.locationAnalysis.amenities} />
              </CardContent>
            </Card>

            {/* 미래 가치 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <TrendingUp className="h-4 w-4" />
                  미래 가치 전망
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs">
                <InfoRow label="개발 호재" text={result.futureProspects.developmentPlan} />
                <InfoRow label="인구 동향" text={result.futureProspects.populationTrend} />
                <InfoRow label="정책 영향" text={result.futureProspects.policyImpact} />
                <InfoRow label="투자 전망" text={result.futureProspects.investmentOutlook} />
              </CardContent>
            </Card>

            {/* 거주자 특징 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Users className="h-4 w-4" />
                  거주자 특징
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 text-xs">
                <InfoRow label="주 연령대" text={result.residents.ageGroup} />
                <InfoRow label="가족 형태" text={result.residents.familyType} />
                <p className="text-muted-foreground leading-relaxed pt-1">{result.residents.summary}</p>
              </CardContent>
            </Card>
          </div>

          {/* 투자 타당성 상세 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">투자 타당성 상세 분석</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-xs">
              <DetailItem label="최소 보유 현금" value={result.investmentFeasibility.minCashRequired} />
              <DetailItem label="대출 한도 (LTV)" value={result.investmentFeasibility.ltv} />
              <DetailItem label="필요 소득 (DSR)" value={result.investmentFeasibility.dsr} />
              <DetailItem label="임대수익률" value={result.investmentFeasibility.rentalYield} />
              <DetailItem label="손익분기점" value={result.investmentFeasibility.breakEvenAnalysis} className="sm:col-span-2 lg:col-span-2" />
            </CardContent>
          </Card>

          {/* 시뮬레이션 안내 */}
          {result.isSimulation && (
            <Alert className="border-amber-500/30 bg-amber-500/5">
              <AlertCircle className="h-4 w-4 text-amber-400" />
              <AlertTitle className="text-amber-400">AI 추정 시뮬레이션 안내</AlertTitle>
              <AlertDescription className="text-muted-foreground text-xs">
                본 분석 결과는 해당 아파트의 정확한 실거래 데이터베이스 대신, {result.dataSource}를 기반으로
                생성된 시뮬레이션입니다. 실제 투자 결정 시에는 국토교통부 실거래가 공개시스템(rt.molit.go.kr)에서
                직접 데이터를 확인하시기 바랍니다.
              </AlertDescription>
            </Alert>
          )}

          <Separator />
        </div>
      )}
    </div>
  );
}

// ── 헬퍼 컴포넌트 ─────────────────────────────────────────────────────
function RiskRow({ label, text }: { label: string; text: string }) {
  return (
    <div className="flex gap-2">
      <span className="shrink-0 font-semibold text-foreground w-20">{label}</span>
      <span className="text-muted-foreground">{text}</span>
    </div>
  );
}

function InfoRow({ label, text }: { label: string; text: string }) {
  return (
    <div className="flex gap-2">
      <span className="shrink-0 font-semibold text-foreground w-14">{label}</span>
      <span className="text-muted-foreground">{text}</span>
    </div>
  );
}

function DetailItem({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={cn('rounded-lg bg-muted/40 p-3', className)}>
      <p className="text-muted-foreground mb-0.5">{label}</p>
      <p className="text-foreground font-medium">{value}</p>
    </div>
  );
}
