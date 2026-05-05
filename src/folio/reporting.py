from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import Position, Snapshot

DEFAULT_INVESTOR_CONTEXT = """goal: "10년 내 자산 3억 달성, 연평균 수익률 12%+ 목표"
horizon: "장기 (10년+), 단 현금흐름 일부는 중기(3-5년)"
risk_tolerance: "중상 (-25% drawdown까지 견딜 수 있음)"
liquidity_need: "월 50만원 정기투입, 비상자금 별도"
income_status: "급여소득자, 안정적"
tax_bracket: "종합소득세 24% 구간 추정, 금융소득종합과세 비대상"
constraints:
  - "해외주식 양도세 250만원 공제 활용"
  - "ISA 계좌 한도 별도 운영"
  - "단일 종목 15% 한도, 단일 테마 40% 한도"
investment_style: "유동성 테제 기반 매크로 + 테마 ETF 위주, 개별주식 보조"
known_biases:
  - "한국 시장 home bias 가능성"
  - "조선/방산 등 정책 수혜주에 과민"
"""


DEFAULT_MACRO_VIEW = """macro_view:
  - "작성자 가설: 전쟁 소강상태 가능성"
  - "작성자 가설: 미국 통화량 증대 가능성"
  - "작성자 가설: 국내 증시는 5월 중반까지 상승 가능성"
emerging_concerns:
  - "레버리지 ETF 비중 확대에 따른 변동성 증가"
  - "국내 시장 및 반도체/테마 ETF 집중"
opportunities_watching:
  - "유동성 확대 시 위험자산 랠리 지속 여부"
  - "상승 후 레버리지 비중 관리 기회"
"""


REPORT_TEMPLATE = """---
type: portfolio-analysis-report
input_snapshot: portfolio_snapshot.md
report_period: {period}
report_date: {report_date}
analyst: OpenRouter LLM
lenses_applied: [risk, macro, value, momentum, behavioral, tax, devils-advocate]
schema_version: 1.0
---

# Portfolio Analysis Report — {period}

## Executive Summary (3줄 요약)

- **현재 상태**:
- **핵심 관찰**:
- **권고 우선순위**:

## Health Score

| 차원 | 점수 | 코멘트 |
|---|---:|---|
| 분산화 (Diversification) | X/5 | |
| 가설 명확성 (Thesis Clarity) | X/5 | |
| 매매 규율 (Discipline) | X/5 | |
| 비용 효율 (Cost Efficiency) | X/5 | |
| 데이터 품질 (Data Quality) | X/5 | |
| **종합** | **X/5** | |

## Lens-by-Lens Findings

### Risk Manager
### Macro Strategist
### Value Discipline
### Momentum/Trend
### Behavioral Coach
### Tax & Cashflow
### Devil's Advocate

## Action Items

모든 액션은 trigger + action + size를 포함해야 한다.

### 즉시 (이번 주)
| # | Trigger (조건) | Action (실행) | Size (규모) | Lens |
|---|---|---|---|---|

### 단기 (1개월 이내)
| # | Trigger | Action | Size | Lens |
|---|---|---|---|---|

### 중기 (분기 이내)
| # | Trigger | Action | Size | Lens |
|---|---|---|---|---|

### 전략적 검토 (반기/연간)
| # | Trigger | Action | Size | Lens |
|---|---|---|---|---|

## 다음 점검 시 확인할 가설/지표

## Open Questions

## 부록: 정량 지표 모음

## 변화 추적 (Diff vs Last Month)

## Disclaimer

이 리포트는 LLM 기반 자동 분석이며 투자 권유나 자문이 아니다.
"""


SYSTEM_PROMPT = """당신은 한국 개인투자자의 포트폴리오를 분석하는 분석가다.

원칙:
1. 사실(Snapshot 데이터)과 해석(분석)을 명확히 구분하라.
2. 근거가 없으면 "데이터 부족"이라고 말하라. 추측하지 마라.
3. 의견을 단정하지 말고, 가능성·확률·시나리오로 표현하라.
4. 한국 시장 맥락(세제, 거래시간, 정책 환경)을 반영하라.
5. 투자자의 risk_tolerance, horizon, constraints를 항상 참조하라.
6. 확증편향 검증 — 좋은 결과가 운인지 실력인지 늘 의심하라.
7. 모든 권고는 구체적이고 실행가능해야 한다.
8. 모든 권고는 trigger(언제) + action(무엇을) + size(얼마나)을 포함하라.
9. 신규 종목 매수 권유는 하지 말고, 보유 포지션 관리·리밸런싱·검증 규칙 위주로 작성하라.
"""


LENS_LIBRARY = """적용할 분석 렌즈:

1. Risk Manager
- HHI, Top 3 비중, 단일 테마 노출, 숨은 상관관계, 꼬리 리스크를 점검한다.

2. Macro Strategist
- 작성자 macro_view와 실제 포지션의 일관성을 검증한다.
- 각 포지션이 민감한 매크로 변수를 매핑한다.

3. Value Discipline
- 가격/가치 판단에 필요한 데이터가 없으면 데이터 부족으로 표기한다.
- +30% 이상 수익 포지션과 -20% 이상 손실 포지션의 가설 손상 여부를 본다.

4. Momentum/Trend
- 수익률과 비중 변화 기준으로 추세 강도를 분류한다.
- 가격 손절선 또는 비중 상한이 없는 포지션을 찾는다.

5. Behavioral Coach
- home bias, recency bias, 확증편향, 처분효과 가능성을 검토한다.
- transaction/journal 데이터가 없으면 판단보류로 표기한다.

6. Tax & Cashflow
- 실현손익/배당 데이터가 없으면 추정하지 않는다.
- 현금 비중과 정기투입 계획의 정합성을 본다.

7. Devil's Advocate
- 가장 자신있는 가설이 틀리는 bear case를 제시한다.
- 포트폴리오가 동시에 흔들릴 수 있는 시나리오를 제시한다.
"""


@dataclass(frozen=True)
class ReportPaths:
    snapshot_path: Path
    briefs_path: Path
    multi_agent_path: Path
    visual_path: Path
    report_path: Path


def default_report_paths(output_dir: Path, period: str) -> ReportPaths:
    period_dir = output_dir / period
    return ReportPaths(
        snapshot_path=period_dir / "portfolio_snapshot.md",
        briefs_path=period_dir / "portfolio_agent_briefs.md",
        multi_agent_path=period_dir / "portfolio_multi_agent_runs.md",
        visual_path=period_dir / "portfolio_visual.svg",
        report_path=period_dir / "portfolio_analysis_report.md",
    )


def render_snapshot_markdown(
    snapshot: Snapshot,
    period: str,
    report_date: date,
    investor_id: str = "hjongc",
    investor_context: str = DEFAULT_INVESTOR_CONTEXT,
    macro_view: str = DEFAULT_MACRO_VIEW,
) -> str:
    balance = snapshot.balance
    asset_total = balance.asset_total
    cash_weight = safe_ratio(balance.cash, asset_total)
    position_count = len(balance.positions)
    positions = sorted_positions(balance.positions)
    position_rows = "\n".join(
        render_position_row(position, asset_total) for position in positions
    )
    cash_row = (
        f"| (CASH) | 예수금 | 현금 | KR | 현금 | - | - | - | "
        f"{balance.cash:,.0f} | - | {cash_weight:.1%} | - |"
    )
    allocation_rows = render_allocation_rows(balance.positions, balance.cash, asset_total)
    sector_rows = render_sector_rows(balance.positions, asset_total)

    return f"""---
type: portfolio-snapshot
report_period: {period}
report_date: {report_date.isoformat()}
base_currency: KRW
benchmark_primary: KOSPI
benchmark_secondary: S&P500
investor_id: {investor_id}
schema_version: 1.0
---

# Portfolio Snapshot — {period}

> 이 문서의 역할: LLM 분석의 입력 데이터(input). 사실(fact)만 기록.
> 작성 빈도: 월 1회 또는 주요 의사결정 전.
> 주의: 이 파일에는 해석을 쓰지 않는다. 해석은 분석 렌즈가 담당한다.

## 1. 투자자 컨텍스트 (Context)

```yaml
{investor_context.rstrip()}
```

## 2. 계좌 요약 KPI

| 항목 | 값 | 이전월 | MoM |
|---|---:|---:|---:|
| 총 평가금액 (₩) | {balance.eval_total:,.0f} | 데이터 부족 | 데이터 부족 |
| 예수금 (₩) | {balance.cash:,.0f} | 데이터 부족 | 데이터 부족 |
| 총 자산 (₩) | {asset_total:,.0f} | 데이터 부족 | 데이터 부족 |
| 누적 원금 입금 (₩) | 데이터 부족 | 데이터 부족 | 데이터 부족 |
| 누적 손익 (₩) | {balance.pnl_total:,.0f} | 데이터 부족 | 데이터 부족 |
| 누적 수익률 | 데이터 부족 | 데이터 부족 | 데이터 부족 |
| MTD 수익률 | 데이터 부족 | - | - |
| YTD 수익률 | 데이터 부족 | - | - |
| 보유 종목 수 | {position_count} | 데이터 부족 | 데이터 부족 |
| 현금 비중 | {cash_weight:.1%} | 데이터 부족 | 데이터 부족 |

## 3. 보유 포지션 (Holdings)

| 티커 | 종목명 | 자산군 | 지역 | 테마 | 수량 | 평균가 | 현재가 | 평가 | 손익률 | 비중 | 기간 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
{position_rows}
{cash_row}

## 4. 자산 배분 (Allocation)

### 자산군별
| 분류 | 비중 | 목표 | 갭 |
|---|---:|---:|---:|
{allocation_rows}

### 지역별
| 분류 | 비중 |
|---|---:|
| 국내 | {safe_ratio(balance.eval_total, asset_total):.1%} |
| 미국 | 0.0% |
| 현금 | {cash_weight:.1%} |

### 섹터·테마별
| 분류 | 비중 | 비고 |
|---|---:|---|
{sector_rows}

### 통화별
| 분류 | 비중 |
|---|---:|
| KRW | 100.0% |
| USD | 0.0% |

## 5. 시계열 (Time Series, 최근 12개월)

데이터 부족: 현재 DB에는 일별/월별 입출금, 월수익률, 벤치마크 수익률이 충분히 누적되어 있지 않다.

**파생 지표**
- HHI: {snapshot.metrics.hhi:.3f}
- Top 3 비중: {snapshot.metrics.top_n_pct:.1%}
- 월수익률 표준편차: 데이터 부족
- 최대 월간 손실: 데이터 부족

## 6. 당월 매매 이력

데이터 부족: KIS 거래내역 연동이 아직 리포트 입력에 포함되지 않았다.

## 7. 배당 (Dividends)

데이터 부족: 배당 수령 데이터가 아직 리포트 입력에 포함되지 않았다.

## 8. 가설 트래커 (Active Theses)

```yaml
theses:
  - id: T1
    name: "국내 증시/반도체/테마 강세 지속"
    positions: [{top_codes(balance.positions, 5)}]
    weight_total: "{snapshot.metrics.top_n_pct:.1%} (상위 3종목 기준)"
    invalidation:
      - "KOSPI 상승 추세 둔화"
      - "외국인 반도체 순매수 둔화"
      - "레버리지 ETF 합산 비중이 투자자 허용 범위를 초과"
    confidence: medium
  - id: T2
    name: "현금 대기 + 변동성 대응"
    positions: ["(CASH)"]
    weight_total: "{cash_weight:.1%}"
    invalidation:
      - "현금 비중이 목표 수익률 달성에 구조적 부담으로 확인"
    confidence: medium
```

## 9. 시장 컨텍스트 (Optional, 작성자 관찰)

```yaml
{macro_view.rstrip()}
```

## 10. 메타 정보

```yaml
data_quality:
  positions_complete: true
  transactions_complete: false
  dividends_complete: false
  benchmark_data: false
  known_gaps:
    - "입출금/원금 데이터"
    - "월별 수익률 및 벤치마크"
    - "거래내역"
    - "배당"
    - "세금 계산용 실현손익"
last_full_review: "데이터 부족"
next_full_review: "다음 월말"
```
"""


def render_report_prompt(
    snapshot_markdown: str,
    period: str,
    report_date: date,
    agent_briefs_markdown: str = "",
) -> str:
    return f"""아래 portfolio_snapshot.md를 분석한다.

1. 7개 렌즈 모두 적용:
   - Risk Manager
   - Macro Strategist
   - Value Discipline
   - Momentum/Trend
   - Behavioral Coach
   - Tax & Cashflow
   - Devil's Advocate

2. 렌즈별 핵심 발견 1-2개씩 추출한다.
3. 아래 report_template.md 형식으로 통합 리포트를 작성한다.
4. 모든 권고는 trigger(언제) + action(무엇) + size(얼마)를 명시한다.
5. 데이터가 없으면 반드시 "데이터 부족"이라고 쓴다.
6. 마지막에 "다음 달 점검 시 확인할 가설/지표 리스트"를 첨부한다.
7. portfolio_agent_briefs.md가 제공되면, 이를 TradingAgents식 분석가/토론 브리프로 간주하고
   Lens-by-Lens Findings와 Action Items에 반영한다.

analysis_lens_library.md:

{LENS_LIBRARY}

report_template.md:

{REPORT_TEMPLATE.format(period=period, report_date=report_date.isoformat())}

portfolio_snapshot.md:

{snapshot_markdown}

portfolio_agent_briefs.md:

{agent_briefs_markdown or "데이터 부족"}
"""


def sorted_positions(positions: list[Position]) -> list[Position]:
    return sorted(positions, key=lambda position: position.eval_amount, reverse=True)


def render_position_row(position: Position, asset_total: float) -> str:
    asset_class = infer_asset_class(position)
    return (
        f"| {position.code} | {position.name} | {asset_class} | KR | {position.sector} | "
        f"{position.qty:,} | {position.avg_price:,.0f} | {position.current_price:,.0f} | "
        f"{position.eval_amount:,.0f} | {position.pnl_pct:+.2f}% | "
        f"{safe_ratio(position.eval_amount, asset_total):.1%} | 데이터 부족 |"
    )


def render_allocation_rows(
    positions: list[Position], cash: float, asset_total: float
) -> str:
    amounts: dict[str, float] = defaultdict(float)
    for position in positions:
        amounts[infer_asset_class(position)] += position.eval_amount
    amounts["현금"] += cash
    return "\n".join(
        f"| {name} | {safe_ratio(amount, asset_total):.1%} | 데이터 부족 | 데이터 부족 |"
        for name, amount in sorted(amounts.items(), key=lambda item: item[0])
    )


def render_sector_rows(positions: list[Position], asset_total: float) -> str:
    amounts: dict[str, float] = defaultdict(float)
    for position in positions:
        amounts[position.sector or "Unknown"] += position.eval_amount
    return "\n".join(
        f"| {sector} | {safe_ratio(amount, asset_total):.1%} | KIS 현재가 업종명 기준 |"
        for sector, amount in sorted(amounts.items(), key=lambda item: item[1], reverse=True)
    )


def infer_asset_class(position: Position) -> str:
    text = f"{position.code} {position.name} {position.sector}".upper()
    if "ETF" in text or "KODEX" in text or "TIGER" in text or "ACE" in text or "SOL" in text:
        return "ETF"
    return "주식"


def top_codes(positions: list[Position], limit: int) -> str:
    return ", ".join(f'"{position.code}"' for position in sorted_positions(positions)[:limit])


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
