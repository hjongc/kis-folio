from __future__ import annotations

from .models import Balance, Metrics


def render_text_dashboard(balance: Balance, metrics: Metrics) -> None:
    print("folio dashboard")
    print(f"account={balance.account_id}")
    print(
        f"eval_total={balance.eval_total:,.0f} "
        f"cash={balance.cash:,.0f} pnl={balance.pnl_total:,.0f}"
    )
    print(f"hhi={metrics.hhi:.3f} top3={metrics.top_n_pct:.1%}")
    print("positions:")
    for position in sorted(balance.positions, key=lambda item: item.eval_amount, reverse=True):
        weight = metrics.position_weights.get(position.code, 0.0)
        print(
            f"- {position.code} {position.name} "
            f"weight={weight:.1%} eval={position.eval_amount:,.0f} "
            f"pnl={position.pnl:,.0f} sector={position.sector}"
        )
    print(
        "[A] analyze: run `folio analyze --mock`  "
        "[R] refresh: run `folio status --mock`  [Q] quit"
    )


def run_dashboard(balance: Balance, metrics: Metrics) -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import DataTable, Footer, Header, Static
    except ImportError:
        render_text_dashboard(balance, metrics)
        return

    class FolioDashboard(App[None]):
        CSS = """
        Screen {
            layout: vertical;
        }
        #metrics {
            height: 3;
            padding: 0 1;
            background: $surface;
        }
        #body {
            height: 1fr;
        }
        #sectors {
            width: 34;
            padding: 1;
            background: $panel;
        }
        DataTable {
            height: 1fr;
        }
        """
        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "refresh", "Refresh"),
            ("a", "analyze", "Analyze"),
        ]

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            yield Static(
                (
                    f"평가금액 {balance.eval_total:,.0f}원 | "
                    f"평가손익 {balance.pnl_total:,.0f}원 | "
                    f"현금 {balance.cash:,.0f}원 | HHI {metrics.hhi:.3f}"
                ),
                id="metrics",
            )
            with Horizontal(id="body"):
                table = DataTable()
                table.add_columns("코드", "이름", "비중", "평가금액", "손익", "섹터")
                positions = sorted(
                    balance.positions, key=lambda item: item.eval_amount, reverse=True
                )
                for position in positions:
                    table.add_row(
                        position.code,
                        position.name,
                        f"{metrics.position_weights.get(position.code, 0.0):.1%}",
                        f"{position.eval_amount:,.0f}",
                        f"{position.pnl:,.0f}",
                        position.sector,
                    )
                yield table
                sector_lines = ["섹터 분포"]
                for sector, weight in metrics.sector_dist.items():
                    sector_lines.append(f"{sector}: {weight:.1%}")
                with Vertical(id="sectors"):
                    yield Static("\n".join(sector_lines))
            yield Footer()

        def action_refresh(self) -> None:
            self.notify("CLI에서 `folio status`로 최신 스냅샷을 조회하세요.")

        def action_analyze(self) -> None:
            self.notify("CLI에서 `folio analyze`로 Advisor 분석을 실행하세요.")

    FolioDashboard().run()
