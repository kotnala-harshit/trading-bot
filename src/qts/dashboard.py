"""One read-only phase model for Pages and Streamlit; missing evidence stays missing."""
from __future__ import annotations

import csv
import html
import json
from datetime import UTC, datetime
from pathlib import Path

from qts.platform import PHASES, load_phases, promotion_status


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def phase_snapshot(root: Path, phase: str, legacy: dict | None = None) -> dict:
    config = load_phases(root)
    settings = config[phase]
    live = read_json(root / "runtime" / f"{phase}_platform.json")
    filename = "paper_state.json" if phase == "india" else "us_paper_state.json"
    state = live.get("state") or (legacy if legacy is not None else read_json(root / "runtime" / filename) if phase != "global" else {})
    capital = settings["capital"]
    cash = state.get("cash")
    quotes = live.get("quotes", {})
    positions = []
    equity = state.get("last_equity")
    if live:
        equity = cash + sum(p["quantity"] * quotes[s]["last"] for s, p in state.get("positions", {}).items())
    for symbol, item in state.get("positions", {}).items():
        price = quotes.get(symbol, {}).get("last", item.get("last_price"))
        rank = item.get("rank")
        positions.append({"symbol": symbol, "quantity": item["quantity"], "entry_price": item["entry_price"],
                          "current_price": price, "target_weight": item.get("target_weight"),
                          "actual_weight": item["quantity"] * price / equity if price and equity else None,
                          "score": item.get("score"), "rank": rank,
                          "state": "UNRANKED" if rank is None else "KEEP" if rank <= 5 else "WATCH" if rank <= settings["keep_rank"] else "SELL"})
    last_quote = min((q["timestamp"] for q in quotes.values()), default=state.get("latest_data_at"))
    age = None
    if last_quote:
        age = (datetime.now(UTC) - datetime.fromisoformat(last_quote)).total_seconds()
    ledger_path = root / "runtime" / ("paper_ledger.csv" if phase == "india" else "us_paper_ledger.csv")
    fills = []
    if phase != "global" and ledger_path.exists() and not live:
        with ledger_path.open() as handle:
            fills = list(csv.DictReader(handle))
    orders = live.get("last_result", {}).get("orders", [])
    reconciliation = live.get("reconciliation", {})
    exposure = (equity - cash) / equity if equity and cash is not None else None
    history = state.get("equity_history", [])
    benchmark = (history[-1]["nifty"] / history[0]["nifty"] - 1) if len(history) > 1 else None
    total_return = equity / capital - 1 if equity is not None else None
    peak = max([capital] + [x["equity"] for x in history] + ([equity] if equity else []))
    drawdown = equity / peak - 1 if equity else None
    max_dd = None
    if history:
        high, max_dd = capital, 0.0
        for point in history:
            high = max(high, point["equity"])
            max_dd = min(max_dd, point["equity"] / high - 1)
    metrics = {"starting_capital": capital, "portfolio_value": equity, "cash": cash,
               "gross_exposure": exposure, "net_exposure": exposure,
               "cumulative_pnl": equity - capital if equity is not None else None,
               "daily_pnl": None, "realized_pnl": state.get("realized_pnl"),
               "unrealized_pnl": sum(p["quantity"] * (p["current_price"] - p["entry_price"]) for p in positions) if positions and all(p["current_price"] is not None for p in positions) else None,
               "benchmark_return": benchmark, "excess_performance": total_return - benchmark if total_return is not None and benchmark is not None else None,
               "current_drawdown": drawdown, "maximum_drawdown": max_dd,
               "total_fees": state.get("fees", sum(float(f["fees"]) for f in fills) if fills else None)}
    for key in ("volatility", "sharpe", "sortino", "calmar", "profit_factor", "expectancy", "turnover",
                "estimated_spread_cost", "slippage", "implementation_shortfall"):
        metrics[key] = None
    for metric, field in [("estimated_spread_cost", "spread_cost"), ("slippage", "slippage"), ("implementation_shortfall", "implementation_shortfall")]:
        if live.get("fills"):
            metrics[metric] = sum(f[field] for f in live["fills"])
    research = read_json(root / "artifacts/rebuild_results.json").get(phase, {})
    return {"research": research, "phase": phase, "currency": settings["currency"], "environment": live.get("environment", "PAPER" if state else "RESEARCH"),
            "provider": live.get("provider", "Yahoo Finance" if state else "Not connected"),
            "data_mode": live.get("data_mode", "delayed" if state else "historical"),
            "execution": "INTERNAL PAPER", "transmit_orders": False,
            "reconciliation": "PASS" if reconciliation.get("matched") is True else "FAIL / NOT VERIFIED",
            "reconciliation_differences": reconciliation or "Legacy account has not been independently reconciled",
            "last_quote": last_quote, "quote_age_seconds": age, "api_latency_ms": None,
            "market_open": "UNKNOWN — official session feed not connected",
            "promotion": promotion_status({}, config["promotion"]), "metrics": metrics, "holdings": positions,
            "orders": orders, "legacy_fills": fills[-12:], "candidates": state.get("rankings", []),
            "next_review_sessions": max(0, settings["review_sessions"] - state.get("sessions_since_review", 0)) if state else None,
            "last_successful_run": state.get("last_successful_scan", live.get("last_run")),
            "last_failed_run": None, "errors_last_24h": None, "next_expected_run": "Not scheduled for validated execution",
            "data_quality": "STALE" if age is not None and age > 60 else "NOT VERIFIED" if not live else "Validated at last execution attempt; see order status",
            "missing_stale_quotes": "No executable quote feed" if not quotes else [s for s, q in quotes.items() if (datetime.now(UTC) - datetime.fromisoformat(q["timestamp"])).total_seconds() > 60],
            "corporate_action_warnings": "Official reconciliation required; legacy Yahoo adjustment audit outstanding",
            "system_health": "BLOCKED" if not live else live["last_result"]["status"],
            "status": ("Legacy execution retired; preserved observations only. Last recorded status: " + state.get("status", "Unknown")) if state and not live else state.get("status", "Research only; no paper account activated"),
            "universe": settings.get("markets", settings.get("etfs", settings["universe"])),
            "history": history}


def display(value) -> str:
    if value is None:
        return "Not measured"
    if isinstance(value, float):
        return f"{value:,.4f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No records available.</p>"
    keys = list(rows[0])
    return "<div class='scroll'><table><thead><tr>" + "".join(f"<th>{html.escape(k.replace('_', ' '))}</th>" for k in keys) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{html.escape(display(row.get(k)))}</td>" for k in keys) + "</tr>" for row in rows) + "</tbody></table></div>"



def performance_chart(history: list) -> str:
    if len(history) < 2:
        return "<p>Insufficient recorded observations for a performance chart.</p>"
    series = [[p["equity"] / history[0]["equity"] - 1 for p in history],
              [p["nifty"] / history[0]["nifty"] - 1 for p in history]]
    low, high = min(map(min, series)), max(map(max, series))
    span = high - low or .01
    lines = []
    for values, color in zip(series, ["#176a90", "#828a92"]):
        points = " ".join(f"{50 + i / (len(values)-1) * 700:.1f},{220-(v-low)/span*180:.1f}" for i,v in enumerate(values))
        lines.append(f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{points}'/>")
    return f"<svg viewBox='0 0 800 260' role='img' aria-label='Recorded portfolio and Nifty price-index return by scan'><text x='5' y='25'>{high:.1%}</text><text x='5' y='220'>{low:.1%}</text>{''.join(lines)}<text x='50' y='250'>Recorded scans (chronological)</text></svg><p>Blue: portfolio. Gray: Nifty price index. Return since first recorded scan; {html.escape(history[0]['timestamp'][:10])} to {html.escape(history[-1]['timestamp'][:10])}. Uneven scan intervals are equally spaced.</p>"

def render_dashboard(root: Path, path: Path, india_state=None, quotes=None) -> None:
    panels = []
    titles = ["India · Phase 1", "US equities · Phase 2", "Other global markets · Phase 3"]
    for phase, title in zip(PHASES, titles):
        snapshot = phase_snapshot(root, phase, india_state if phase == "india" else None)
        safety = {"ENVIRONMENT": snapshot["environment"], "MARKET DATA": snapshot["data_mode"].upper(),
                  "EXECUTION": "INTERNAL PAPER", "LIVE ORDERS": "DISABLED", "TRANSMIT_ORDERS": "FALSE", "RECONCILIATION": snapshot["reconciliation"]}
        cards = "".join(f"<div><small>{k}</small><strong>{html.escape(v)}</strong></div>" for k, v in safety.items())
        metrics = table([{"metric": k.replace('_', ' '), f"value ({snapshot['currency']}; ratios as decimals)": v} for k, v in snapshot["metrics"].items()])
        health_keys = ["provider", "last_quote", "quote_age_seconds", "api_latency_ms", "market_open", "next_review_sessions", "last_successful_run", "last_failed_run", "errors_last_24h", "next_expected_run", "data_quality", "missing_stale_quotes", "corporate_action_warnings", "reconciliation_differences", "system_health"]
        health = table([{"check": k.replace('_', ' '), "observation": snapshot[k]} for k in health_keys])
        featured = "".join(f"<div><small>{label}</small><strong>{html.escape(display(snapshot['metrics'][key]))}</strong></div>" for key, label in [("portfolio_value", "Portfolio value · " + snapshot["currency"]), ("cash", "Available cash"), ("cumulative_pnl", "Cumulative P&L"), ("current_drawdown", "Drawdown · decimal ratio")])
        research_rows = [{"window": k, "total_return": v["total_return"], "cagr": v["cagr"], "benchmark_cagr": v["benchmark_cagr"], "max_drawdown": v["max_drawdown"], "trades": v["trades"], "win_rate": v["win_rate"]} for k, v in snapshot["research"].get("windows", {}).items()]
        cost_rows = [{"one_way_bps": k, "cagr": v["cagr"], "max_drawdown": v["max_drawdown"]} for k, v in snapshot["research"].get("cost_stress", {}).items()]
        chart = performance_chart(snapshot["history"])
        panels.append(f"""<section id='{phase}' class='phase' {'hidden' if phase != 'india' else ''}>
<h1>{title}</h1><p>{html.escape(snapshot['status'])}</p><div class='safety'>{cards}</div>
<p class='warning'>Promotion: {snapshot['promotion']['status']} · Real-money transmission disabled. Legacy observations are not validated live-data paper evidence.</p>
<div class='featured'>{featured}</div><article><h2>Portfolio performance</h2>{chart}<details><summary>All performance metrics</summary>{metrics}</details></article><details><summary>Risk monitor & system health</summary>{health}</details>
<article><h2>Executed research · diagnostic only</h2>{table(research_rows)}<p>15 bps one-way; adjusted units, current ETF basket. No promotion. Values are decimal ratios; short periods show total return.</p><details><summary>Execution cost stress</summary>{table(cost_rows)}</details></article>
<article><h2>Holdings</h2>{table(snapshot['holdings'])}</article>
<article><h2>Recent activity · order lifecycle</h2>{table(snapshot['orders'])}<h3>Legacy fills — IDs were not recorded</h3>{table(snapshot['legacy_fills'])}<p>ETERNAL's 613 + 1 shares were initial entry and a same-review top-up. Historical rows are preserved.</p></article>
<details><summary>Candidate rankings and universe</summary>{table(snapshot['candidates'])}<p>{html.escape(display(snapshot['universe']))}</p></details>
<details><summary>Independent promotion gates</summary>{table([{'gate': k, 'passed': v} for k,v in snapshot['promotion']['checks'].items()])}</details></section>""")
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Three-phase trading research</title><style>
:root{font:16px system-ui;color:#172433;background:#f2f5f8}*{box-sizing:border-box}body{margin:0}header,main{max-width:1440px;margin:auto;padding:24px}header{border-bottom:1px solid #ccd5df;display:flex;justify-content:space-between;align-items:center}button{font:inherit;padding:12px 24px;background:white;border:1px solid #9eafbe;cursor:pointer}button[aria-pressed=true]{background:#173954;color:white}h1{font-size:28px}h2{font-size:20px}p{line-height:1.5;color:#4a5b6a}.safety{display:grid;grid-template-columns:repeat(3,1fr);background:#102c43;color:white;gap:24px;padding:24px;margin:24px 0}.safety strong{display:block;margin-top:8px;font-size:18px}.safety small{font-size:14px;color:#bbd1e3}.warning{border-left:4px solid #be7400;background:#fff4d9;padding:16px}.featured{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin:24px 0}.featured strong{display:block;font-size:24px;margin-top:10px}.featured small{font-size:14px}svg{width:100%;max-height:280px}article,details{background:white;border:1px solid #d5dee6;margin-bottom:20px;padding:20px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #e2e8ef;padding:10px;max-width:460px;overflow-wrap:anywhere}th{text-transform:capitalize}summary{cursor:pointer;font-weight:600}button:focus-visible,summary:focus-visible{outline:3px solid #ce8509;outline-offset:3px}@media(max-width:800px){.featured{grid-template-columns:1fr 1fr}.safety{grid-template-columns:1fr 1fr}header{display:block}nav{display:flex;margin-top:20px}button{padding:12px}main{padding:14px}}@media(max-width:440px){.safety{grid-template-columns:1fr}}
</style></head><body><header><strong>Trading research / Paper operations</strong><nav aria-label="Trading phases"><button data-phase="india" aria-pressed="true">INDIA</button><button data-phase="us" aria-pressed="false">US</button><button data-phase="global" aria-pressed="false">GLOBAL</button></nav></header><main>""" + "".join(panels) + """<p>Generated snapshot; quote age is measured at generation. Reloading does not fetch live quotes. Historical results are not guarantees.</p></main><script>document.querySelectorAll('[data-phase]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.phase').forEach(p=>p.hidden=p.id!==b.dataset.phase);document.querySelectorAll('[data-phase]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));});</script></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render_dashboard(root, root / "docs/index.html")
