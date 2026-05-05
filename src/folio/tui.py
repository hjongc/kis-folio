from __future__ import annotations

from .models import Balance, Metrics
from .terminal import build_terminal_dashboard, text_bar


def render_text_dashboard(balance: Balance, metrics: Metrics) -> None:
    dashboard = build_terminal_dashboard(balance, metrics)
    print("kis-folio dashboard")
    print(f"account={dashboard.account_id}")
    print(
        f"assets={dashboard.asset_total:,.0f} "
        f"invested={dashboard.eval_total:,.0f} cash={dashboard.cash:,.0f} "
        f"pnl={dashboard.pnl_total:,.0f}"
    )
    print(
        f"stance={dashboard.overall_action} | {dashboard.overall_reason} | "
        f"hhi={dashboard.hhi:.3f} top3={dashboard.top3:.1%} "
        f"leverage={dashboard.leverage_weight:.1%}"
    )
    print("allocation:")
    for label, ratio in dashboard.allocation_bars:
        print(f"- {label:<8} [{text_bar(ratio)}] {ratio:>6.1%}")
    print("positions:")
    for row in dashboard.positions:
        print(
            f"- {row.code:<6} {row.name[:18]:<18} {row.action:<8} "
            f"w={row.weight:>5.1%} pnl={row.pnl_pct:>+7.2f}% "
            f"eval={row.eval_amount:>12,.0f} | {row.reason}"
        )
    print("[R] refresh  [A] agentic report  [V] view latest report  [Q] quit")


def run_dashboard(balance: Balance, metrics: Metrics) -> None:
    dashboard = build_terminal_dashboard(balance, metrics)
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import DataTable, Footer, Header, Label, Static, TabbedContent, TabPane
    except ImportError:
        render_text_dashboard(balance, metrics)
        return

    class FolioDashboard(App[None]):
        CSS = """
        Screen {
            layout: vertical;
        }
        .card {
            height: auto;
            padding: 1 2;
            border: round $primary;
            margin: 0 1 1 1;
        }
        .muted {
            color: $text-muted;
        }
        DataTable {
            height: 1fr;
        }
        #overview-grid {
            height: auto;
        }
        #left {
            width: 1fr;
        }
        #right {
            width: 1fr;
        }
        """
        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "refresh", "Refresh"),
            ("a", "agentic", "Agent Report"),
            ("v", "view_report", "View Report"),
        ]

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with TabbedContent():
                with TabPane("Overview", id="overview"):
                    with Horizontal(id="overview-grid"):
                        with Vertical(id="left"):
                            yield Static(
                                (
                                    f"[b]Total[/b] {dashboard.asset_total:,.0f} KRW\n"
                                    f"[b]Invested[/b] {dashboard.eval_total:,.0f} KRW\n"
                                    f"[b]Cash[/b] {dashboard.cash:,.0f} KRW\n"
                                    f"[b]PnL[/b] {dashboard.pnl_total:,.0f} KRW"
                                ),
                                classes="card",
                            )
                            yield Static(
                                (
                                    f"[b]Overall[/b] {dashboard.overall_action}\n"
                                    f"{dashboard.overall_reason}\n\n"
                                    f"HHI {dashboard.hhi:.3f} | Top3 {dashboard.top3:.1%} | "
                                    f"Leverage {dashboard.leverage_weight:.1%}"
                                ),
                                classes="card",
                            )
                        with Vertical(id="right"):
                            allocation_lines = ["[b]Allocation[/b]"]
                            for label, ratio in dashboard.allocation_bars:
                                allocation_lines.append(
                                    f"{label:<8} {text_bar(ratio, width=18)} {ratio:>6.1%}"
                                )
                            yield Static("\n".join(allocation_lines), classes="card")
                            yield Static(
                                (
                                    "[b]Workflow[/b]\n"
                                    "r refresh account\n"
                                    "a run agentic report\n"
                                    "v open latest report tab\n"
                                    "q quit"
                                ),
                                classes="card",
                            )
                with TabPane("Holdings", id="holdings"):
                    table = DataTable(zebra_stripes=True)
                    table.add_columns(
                        "Code", "Name", "Action", "Weight", "PnL%", "Eval", "Reason"
                    )
                    for row in dashboard.positions:
                        table.add_row(
                            row.code,
                            row.name,
                            row.action,
                            f"{row.weight:.1%}",
                            f"{row.pnl_pct:+.2f}%",
                            f"{row.eval_amount:,.0f}",
                            row.reason,
                        )
                    yield table
                with TabPane("Agents", id="agents"):
                    yield Static(
                        (
                            "[b]Agent Workflow[/b]\n"
                            "7 analyst fan-out -> bull/bear/risk debate -> PM synthesis\n\n"
                            "Use CLI for now:\n"
                            "folio report --agentic --llm-max-calls 12 --llm-max-cost-usd 1.00"
                        ),
                        classes="card",
                    )
                with TabPane("Report", id="report"):
                    yield Static(
                        (
                            "[b]Latest Report[/b]\n"
                            "reports/<YYYY-MM>/portfolio_analysis_report.md\n\n"
                            "Generated reports stay local and are ignored by Git."
                        ),
                        classes="card",
                    )
                with TabPane("Files", id="files"):
                    yield Label("Generated outputs")
                    yield Static(
                        (
                            "portfolio_snapshot.md\n"
                            "portfolio_agent_briefs.md\n"
                            "portfolio_multi_agent_runs.md\n"
                            "portfolio_workflow_trace.md\n"
                            "portfolio_visual.svg\n"
                            "portfolio_analysis_report.md"
                        ),
                        classes="card",
                    )
            yield Footer()

        def action_refresh(self) -> None:
            self.notify("Run `folio status` to refresh account data.")

        def action_agentic(self) -> None:
            self.notify("Run `folio report --agentic` to generate a LangGraph report.")

        def action_view_report(self) -> None:
            self.notify("Open reports/<YYYY-MM>/portfolio_analysis_report.md.")

    FolioDashboard().run()
