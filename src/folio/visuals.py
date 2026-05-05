from __future__ import annotations

from .agentic import is_leverage_position
from .models import Snapshot
from .reporting import infer_asset_class, safe_ratio, sorted_positions


def render_portfolio_svg(snapshot: Snapshot, width: int = 960, height: int = 620) -> str:
    balance = snapshot.balance
    asset_total = balance.asset_total
    positions = sorted_positions(balance.positions)
    etf = sum(p.eval_amount for p in positions if infer_asset_class(p) == "ETF")
    stock = sum(p.eval_amount for p in positions if infer_asset_class(p) == "주식")
    cash = balance.cash
    leverage = sum(p.eval_amount for p in positions if is_leverage_position(p))

    bars = [
        ("ETF", etf, "#2f6fed"),
        ("주식", stock, "#13a10e"),
        ("현금", cash, "#8a8886"),
        ("레버리지", leverage, "#d13438"),
    ]
    top = positions[:8]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="32" y="42" font-size="24" font-family="Arial" font-weight="700">'
        "folio portfolio visual</text>",
        f'<text x="32" y="72" font-size="14" font-family="Arial" fill="#555">'
        f"총자산 {asset_total:,.0f} KRW · HHI {snapshot.metrics.hhi:.3f} · "
        f"Top3 {snapshot.metrics.top_n_pct:.1%}</text>",
        '<text x="32" y="118" font-size="18" font-family="Arial" font-weight="700">'
        "Asset Allocation</text>",
    ]
    y = 142
    for name, amount, color in bars:
        ratio = safe_ratio(amount, asset_total)
        bar_width = int(520 * ratio)
        lines.extend(
            [
                f'<text x="32" y="{y + 16}" font-size="13" font-family="Arial">{name}</text>',
                f'<rect x="120" y="{y}" width="520" height="22" fill="#eeeeee"/>',
                f'<rect x="120" y="{y}" width="{bar_width}" height="22" fill="{color}"/>',
                f'<text x="656" y="{y + 16}" font-size="13" font-family="Arial">'
                f"{ratio:.1%}</text>",
            ]
        )
        y += 38

    lines.append(
        '<text x="32" y="326" font-size="18" font-family="Arial" font-weight="700">'
        "Top Positions</text>"
    )
    y = 350
    for position in top:
        ratio = safe_ratio(position.eval_amount, asset_total)
        bar_width = int(520 * ratio)
        color = "#d13438" if is_leverage_position(position) else "#605e5c"
        label = f"{position.code} {position.name[:18]}"
        lines.extend(
            [
                f'<text x="32" y="{y + 15}" font-size="12" font-family="Arial">{label}</text>',
                f'<rect x="220" y="{y}" width="420" height="20" fill="#eeeeee"/>',
                f'<rect x="220" y="{y}" width="{bar_width}" height="20" fill="{color}"/>',
                f'<text x="656" y="{y + 15}" font-size="12" font-family="Arial">'
                f"{ratio:.1%}</text>",
            ]
        )
        y += 30
    lines.append("</svg>")
    return "\n".join(lines)

