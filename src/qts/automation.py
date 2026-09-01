from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from qts.paper import apply_corporate_actions, execute_paper_fill, mark_to_market
from qts.providers import yahoo_chart, yahoo_corporate_actions
from qts.strategy import risk_adjusted_momentum_score, volatility_target_exposure

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "runtime" / "paper_state.json"
LEDGER_PATH = ROOT / "runtime" / "paper_ledger.csv"
WATCHLIST_PATH = ROOT / "data" / "indian_watchlist.json"
CONTROL_PATH = ROOT / "configs" / "paper-trader.json"
PAGE_PATH = ROOT / "docs" / "index.html"
US_RESULTS_PATH = ROOT / "artifacts" / "us_phase2_results.json"
US_STATE_PATH = ROOT / "runtime" / "us_paper_state.json"
STARTING_CAPITAL = 1_000_000.0
MAX_POSITIONS = 5
KEEP_RANK = 10
REVIEW_SESSIONS = 60
FEE_BPS = 10.0
MAX_DRAWDOWN = -0.20
COOLDOWN_DAYS = 28


def market_is_open(now: datetime | None = None) -> bool:
    india = (now or datetime.now(UTC)).astimezone(ZoneInfo("Asia/Kolkata"))
    minutes = india.hour * 60 + india.minute
    return india.weekday() < 5 and 9 * 60 + 15 <= minutes <= 15 * 60 + 30


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "cash": STARTING_CAPITAL,
        "positions": {},
        "peak_equity": STARTING_CAPITAL,
        "last_equity": STARTING_CAPITAL,
        "last_run": None,
        "cooldown_until": None,
        "last_scan_date": None,
        "sessions_since_review": REVIEW_SESSIONS,
        "status": "Waiting for first scheduled market-hours run",
    }


def cooldown_active(state: dict, now: datetime) -> bool:
    value = state.get("cooldown_until")
    return bool(value and now < datetime.fromisoformat(value))


def drawdown_stop_triggered(drawdown: float, has_positions: bool) -> bool:
    return has_positions and drawdown <= MAX_DRAWDOWN


def quote_is_current(latest_timestamp, india_day: str) -> bool:
    return latest_timestamp.tz_convert(ZoneInfo("Asia/Kolkata")).date().isoformat() == india_day


def trading_enabled() -> bool:
    return bool(json.loads(CONTROL_PATH.read_text()).get("enabled", False))


def append_fills(fills: list) -> None:
    if not fills:
        return
    exists = LEDGER_PATH.exists()
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", newline="") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(["timestamp", "symbol", "side", "quantity", "price", "fees"])
        for fill in fills:
            writer.writerow(
                [fill.timestamp, fill.symbol, fill.side, fill.quantity, fill.price, fill.fees]
            )


def record_history(state: dict, timestamp: str, nifty: float) -> None:
    history = state.setdefault("equity_history", [])
    history.append({"timestamp": timestamp, "equity": state["last_equity"], "nifty": nifty})
    state["equity_history"] = history[-5000:]


def render_page(state: dict, quotes: dict[str, float]) -> None:
    equity = float(state.get("last_equity", STARTING_CAPITAL))
    cash = float(state.get("cash", STARTING_CAPITAL))
    total_return = equity / STARTING_CAPITAL - 1
    drawdown = equity / max(float(state.get("peak_equity", equity)), equity) - 1
    invested = max(0.0, equity - cash)
    exposure = invested / equity if equity else 0.0
    risk = "High" if drawdown <= -0.10 else "Medium" if drawdown <= -0.04 else "Low"
    positions = []
    for symbol, item in state["positions"].items():
        price = quotes.get(symbol, item.get("last_price", item["entry_price"]))
        value = item["quantity"] * price
        pnl = value - item["quantity"] * item["entry_price"]
        pnl_pct = price / item["entry_price"] - 1
        positions.append(
            f"<tr><td><strong>{html.escape(symbol.replace('.NS', ''))}</strong>"
            f"<small>Momentum selection</small></td><td>{item['quantity']:,.0f}</td>"
            f"<td>₹{item['entry_price']:,.2f}</td><td>₹{price:,.2f}</td>"
            f"<td>{value / equity:.1%}</td><td>₹{value:,.0f}</td>"
            f"<td class='{'positive' if pnl >= 0 else 'negative'}'>₹{pnl:,.0f}<small>{pnl_pct:+.2%}</small></td></tr>"
        )
    rows = "".join(positions) or "<tr><td colspan='7'>No open paper positions</td></tr>"
    activity = []
    if LEDGER_PATH.exists():
        with LEDGER_PATH.open(newline="") as handle:
            fills = list(csv.DictReader(handle))[-8:][::-1]
        for fill in fills:
            activity.append(
                f"<li><span class='trade {fill['side'].lower()}'>{fill['side']}</span>"
                f"<div><strong>{html.escape(fill['symbol'].replace('.NS', ''))}</strong> · "
                f"{float(fill['quantity']):,.0f} shares at ₹{float(fill['price']):,.2f}"
                f"<small>{html.escape(fill['timestamp'][:16].replace('T', ' '))} UTC · fee ₹{float(fill['fees']):,.2f}</small></div></li>"
            )
    activity_rows = "".join(activity) or "<li>No paper transactions yet</li>"
    successful_scan = state.get("last_successful_scan") or "Not completed yet"
    last_attempt = state.get("last_attempt") or state.get("last_run") or "Not run yet"
    chart_data = json.dumps(state.get("equity_history", []), separators=(",", ":"))
    us_results = json.loads(US_RESULTS_PATH.read_text()) if US_RESULTS_PATH.exists() else {}
    us_state = json.loads(US_STATE_PATH.read_text()) if US_STATE_PATH.exists() else {
        "cash": 10_000, "last_equity": 10_000, "positions": {},
        "status": "Waiting for first US market-hours paper run",
    }
    us_holdout = us_results.get("holdout", {})
    us_cagr = us_holdout.get("cagr")
    us_benchmark = us_holdout.get("benchmark_cagr")
    us_drawdown = us_holdout.get("max_drawdown")
    us_win_rate = us_holdout.get("win_rate")
    us_inr = us_holdout.get("inr_cagr")
    us_coverage = us_results.get("price_coverage")
    us_timeline_rows = []
    for label in ("3m", "6m", "9m", "12m", "3y", "5y", "10y"):
        result = us_results.get("timeline", {}).get(label, {})
        short = label.endswith("m")
        win_rate = result.get("win_rate")
        us_timeline_rows.append(
            f"<tr><td><strong>{label.upper()}</strong></td>"
            f"<td>{result.get('total_return' if short else 'cagr', 0):+.2%}</td>"
            f"<td>{result.get('benchmark_total_return' if short else 'benchmark_cagr', 0):+.2%}</td>"
            f"<td>{result.get('inr_total_return' if short else 'inr_cagr', 0):+.2%}</td>"
            f"<td class='negative'>{result.get('max_drawdown', 0):.2%}</td>"
            f"<td>{win_rate:.1%}</td></tr>"
        )
    us_timeline_rows = "".join(us_timeline_rows)
    us_defensive_rows = []
    defensive = us_results.get("risk_reduction_experiment", {}).get("timeline", {})
    for label in ("3m", "6m", "9m", "12m", "3y", "5y", "10y"):
        result = defensive.get(label, {})
        short = label.endswith("m")
        win_rate = result.get("win_rate")
        us_defensive_rows.append(
            f"<tr><td><strong>{label.upper()}</strong></td>"
            f"<td>{result.get('total_return' if short else 'cagr', 0):+.2%}</td>"
            f"<td class='negative'>{result.get('max_drawdown', 0):.2%}</td>"
            f"<td>{f'{win_rate:.1%}' if win_rate is not None else 'No closed trades'}</td>"
            f"<td>{result.get('trades', 0)}</td></tr>"
        )
    us_defensive_rows = "".join(us_defensive_rows)
    page = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Indian Equity Paper Trader</title><style>
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f6f8f5;color:#17201b;font:15px Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}}a{{color:inherit;text-decoration:none}}
.shell{{max-width:1240px;margin:auto;padding:0 24px 48px}}nav{{height:72px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #dde4df}}.brand{{font-size:20px;font-weight:800}}.brand i{{display:inline-block;width:12px;height:12px;background:#00b386;border-radius:4px;margin-right:9px}}.links{{display:flex;gap:24px;color:#59645e}}.links a:hover{{color:#008f6b}}.paper{{background:#daf7ea;color:#087657;padding:8px 12px;border-radius:999px;font-size:12px;font-weight:800}}
header{{display:flex;justify-content:space-between;align-items:end;padding:34px 0 22px}}h1{{font-size:30px;margin:0 0 7px}}h2{{font-size:19px;margin:0}}p{{margin:0;color:#66716b}}.pause{{border:1px solid #e1a18f;background:#fff1ec;color:#9c3d25;padding:10px 14px;border-radius:10px;font-weight:700}}
.markets{{display:flex;gap:8px;margin:0 0 18px;padding:5px;background:#e9eeea;border-radius:12px;width:max-content}}.markets button{{border:0;background:transparent;padding:10px 16px;border-radius:9px;color:#657069;font-weight:700;cursor:pointer}}.markets button.active{{background:#fff;color:#132019;box-shadow:0 3px 12px rgba(28,44,35,.08)}}.market-panel{{display:none}}.market-panel.active{{display:grid}}.phase-hero{{grid-column:span 12;display:flex;justify-content:space-between;align-items:center}}.checklist{{grid-column:span 7}}.roadmap{{grid-column:span 5}}.checklist li{{padding:11px 0;border-bottom:1px solid #edf0ee}}.locked{{background:#f0f2f1;color:#59635d;padding:8px 11px;border-radius:999px;font-size:12px;font-weight:800}}
.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}}.card{{background:#fff;border:1px solid #e3e8e4;border-radius:16px;padding:20px;box-shadow:0 6px 22px rgba(28,44,35,.04)}}.metric{{grid-column:span 3}}.metric small,.muted,td small,.activity small{{display:block;color:#7a857f;margin-top:5px}}.metric strong{{display:block;font-size:25px;margin-top:10px}}.positive,.safe{{color:#008f6b!important}}.negative{{color:#db583c!important}}
.chart{{grid-column:span 8;min-height:355px}}.risk{{grid-column:span 4}}.section-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}}.ranges{{display:flex;gap:5px}}.ranges button{{border:0;background:#f0f4f1;color:#66716b;border-radius:7px;padding:6px 9px;cursor:pointer}}.ranges button.active{{background:#17201b;color:#fff}}canvas{{width:100%;height:255px}}.legend{{display:flex;gap:18px;font-size:12px;color:#66716b}}.legend i{{display:inline-block;width:18px;height:3px;margin-right:6px;vertical-align:middle;background:#00a77b}}.legend .benchmark{{background:#9da7a1}}
.bar{{height:10px;background:#edf1ee;border-radius:999px;overflow:hidden;margin:10px 0 6px}}.bar i{{display:block;height:100%;background:#00b386;border-radius:999px}}.risk-row{{padding:15px 0;border-bottom:1px solid #edf0ee;display:flex;justify-content:space-between}}.risk-row:last-child{{border:0}}.tag{{padding:5px 9px;border-radius:999px;background:#e7f7ef;color:#087657;font-size:12px;font-weight:800}}.tag.medium{{background:#fff3d7;color:#8a6513}}.tag.high{{background:#ffebe5;color:#a33820}}
.holdings{{grid-column:span 8}}.activity{{grid-column:span 4}}table{{border-collapse:collapse;width:100%}}th,td{{padding:13px 10px;border-bottom:1px solid #edf0ee;text-align:right;white-space:nowrap}}th{{font-size:12px;color:#7a857f;font-weight:600}}th:first-child,td:first-child{{text-align:left}}.activity ul{{list-style:none;padding:0;margin:0}}.activity li{{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid #edf0ee}}.trade{{min-width:42px;text-align:center;height:24px;padding:4px;border-radius:6px;font-size:11px;font-weight:800}}.buy{{background:#ddf7ec;color:#087657}}.sell{{background:#ffebe5;color:#a33820}}
.status{{grid-column:span 12;display:flex;justify-content:space-between;gap:22px;align-items:center}}.status-details{{display:flex;gap:26px;flex-wrap:wrap;font-size:13px}}.health{{font-weight:800}}.warning{{margin-top:16px;background:#fff8e8;border:1px solid #f0dfb2;padding:13px 16px;border-radius:12px;color:#735c21}}.stale{{color:#c13d28!important}}
@media(max-width:900px){{.metric{{grid-column:span 6}}.chart,.risk,.holdings,.activity{{grid-column:span 12}}.links{{display:none}}}}@media(max-width:560px){{.shell{{padding:0 14px 32px}}header{{align-items:start;gap:18px}}h1{{font-size:24px}}.metric{{grid-column:span 12}}.status{{display:block}}.status-details{{display:block}}.status-details span{{display:block;margin-top:8px}}.table-wrap{{overflow:auto}}}}
</style></head><body><div class='shell'>
<nav><div class='brand'><i></i>Paperfolio</div><div class='links'><a href='#performance'>Performance</a><a href='#holdings'>Holdings</a><a href='#activity'>Activity</a></div><span class='paper'>PAPER ONLY</span></nav>
<header><div><h1>Indian equity portfolio</h1><p>Automated Nifty 50 momentum research · real orders disabled</p></div><a class='pause' href='https://github.com/kotnala-harshit/trading-bot/edit/main/configs/paper-trader.json'>Pause in GitHub</a></header>
<div class='markets'><button class='active' data-market='india'>India · Phase 1</button><button data-market='us'>US · Phase 2</button><button data-market='global'>Global · Phase 3</button></div>
<main id='india' class='grid market-panel active'>
<section class='card metric'><small>Portfolio value</small><strong>₹{equity:,.0f}</strong><small class='{'positive' if total_return >= 0 else 'negative'}'>{total_return:+.2%} since start</small></section>
<section class='card metric'><small>Invested</small><strong>₹{invested:,.0f}</strong><small>{exposure:.0%} current exposure</small></section>
<section class='card metric'><small>Available cash</small><strong>₹{cash:,.0f}</strong><small>₹{state.get('dividends_received', 0):,.0f} dividends received</small></section>
<section class='card metric'><small>Open positions</small><strong>{len(state['positions'])} / {MAX_POSITIONS}</strong><small>Next review in {max(0, REVIEW_SESSIONS - state.get('sessions_since_review', 0))} sessions</small></section>
<section id='performance' class='card chart'><div class='section-head'><div><h2>Portfolio performance</h2><p>Normalized against Nifty 50 from recorded scans</p></div><div class='ranges'><button data-days='1'>1D</button><button data-days='7'>1W</button><button data-days='30'>1M</button><button data-days='90'>3M</button><button class='active' data-days='0'>All</button></div></div><canvas id='performance-chart'></canvas><div class='legend'><span><i></i>Portfolio</span><span><i class='benchmark'></i>Nifty 50</span></div></section>
<section class='card risk'><div class='section-head'><div><h2>Risk monitor</h2><p>Automatic paper controls</p></div><span class='tag {risk.lower()}'>{risk} risk</span></div>
<div class='risk-row'><span>Current drawdown</span><strong class='{'negative' if drawdown < 0 else 'positive'}'>{drawdown:.2%}</strong></div>
<div class='risk-row'><span>Equity exposure</span><strong>{exposure:.0%}</strong></div><div class='bar'><i style='width:{exposure:.1%}'></i></div><small class='muted'>Volatility target: {state.get('exposure_target', 1):.0%}</small>
<div class='risk-row'><span>Emergency stop</span><strong>20% drawdown</strong></div><div class='risk-row'><span>Cooldown</span><strong>{html.escape(state.get('cooldown_until') or 'Inactive')}</strong></div></section>
<section id='holdings' class='card holdings'><div class='section-head'><div><h2>Holdings</h2><p>Current simulated positions</p></div><span class='tag'>{len(state['positions'])} active</span></div><div class='table-wrap'><table><thead><tr><th>Company</th><th>Shares</th><th>Average</th><th>Latest</th><th>Weight</th><th>Value</th><th>Open P/L</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section id='activity' class='card activity'><div class='section-head'><div><h2>Recent activity</h2><p>Auditable paper fills</p></div></div><ul>{activity_rows}</ul></section>
<section class='card status'><div><h2>System status</h2><p>{html.escape(state['status'])}</p></div><div class='status-details'><span id='schedule-health' class='health' data-scan='{successful_scan}'>Checking schedule…</span><span>Market data<br><strong>{html.escape(state.get('latest_data_at') or 'Not available')}</strong></span><span>Last attempt<br><strong>{html.escape(last_attempt)}</strong></span></div></section>
</main>
<main id='us' class='grid market-panel'><section class='card phase-hero'><div><h2>US equities · Phase 2</h2><p>$10,000 simulated account · real brokerage orders disabled</p></div><span class='paper'>PAPER OBSERVATION ACTIVE</span></section>
<section class='card metric'><small>US paper value</small><strong>${us_state.get('last_equity', 10_000):,.2f}</strong><small>{us_state.get('last_equity', 10_000) / 10_000 - 1:+.2%} since start</small></section><section class='card metric'><small>US paper cash</small><strong>${us_state.get('cash', 10_000):,.2f}</strong><small>Maximum equity exposure: 40%</small></section><section class='card metric'><small>US paper positions</small><strong>{len(us_state.get('positions', {}))} / 5</strong><small>120-session strategy review</small></section><section class='card metric'><small>US automation</small><strong>{us_state.get('exposure_target', 0):.0%}</strong><small>{html.escape(us_state.get('status', 'Waiting'))}</small></section>
<section class='card metric'><small>Holdout annualized · USD</small><strong>{us_cagr:.2%}</strong><small>SPY adjusted: {us_benchmark:.2%}</small></section><section class='card metric'><small>Holdout annualized · INR</small><strong>{us_inr:.2%}</strong><small>SPY plus FX: {us_holdout.get('benchmark_inr_cagr'):.2%}</small></section><section class='card metric'><small>Maximum drawdown</small><strong>{us_drawdown:.2%}</strong><small>SPY adjusted: {us_holdout.get('benchmark_max_drawdown'):.2%}</small></section><section class='card metric'><small>Historical price coverage</small><strong>{us_coverage:.1%}</strong><small>{us_results.get('downloaded_symbols', 0)} / {us_results.get('requested_symbols', 0)} tickers</small></section>
<section class='card checklist'><h2>What the test says</h2><ul><li>Paper observation uses $10,000—not real converted or broker-held funds</li><li>Five-year return trailed SPY and drawdown reached {us_drawdown:.1%}</li><li>{us_win_rate:.1%} of {us_holdout.get('trades', 0)} closed trades were profitable</li><li>{us_results.get('requested_symbols', 0) - us_results.get('downloaded_symbols', 0)} historical symbols failed free-data checks; membership ends {us_results.get('membership_latest')}</li><li>25% treaty withholding is documented but not separable from adjusted prices</li></ul></section><section class='card roadmap'><h2>Safety status</h2><p>Paper observation is active, but promotion remains rejected. No broker credentials or real-order path exist. Disable with <code>us_enabled</code> in the GitHub control file.</p></section>
<section class='card' style='grid-column:span 12'><div class='section-head'><div><h2>Capital-preservation diagnostic</h2><p>7% volatility target · 40% maximum exposure · SPY 200-day EMA cash gate</p></div></div><div class='table-wrap'><table><thead><tr><th>Window</th><th>Strategy USD</th><th>Max drawdown</th><th>Trade win rate</th><th>Closed trades</th></tr></thead><tbody>{us_defensive_rows}</tbody></table></div><p class='warning'>Drawdown moved near 10%, but the 70–80% win target did not hold across horizons. This is diagnostic evidence, not a promoted model.</p></section>
<section class='card' style='grid-column:span 12'><div class='section-head'><div><h2>Unconstrained baseline</h2><p>Month rows show total return; year rows show annualized return</p></div></div><div class='table-wrap'><table><thead><tr><th>Window</th><th>Strategy USD</th><th>SPY USD</th><th>Strategy INR</th><th>Max drawdown</th><th>Trade win rate</th></tr></thead><tbody>{us_timeline_rows}</tbody></table></div></section></main>
<main id='global' class='grid market-panel'><section class='card phase-hero'><div><h2>Other global markets · Phase 3</h2><p>Market-by-market research, never one mixed unvalidated pool</p></div><span class='locked'>RESEARCH LOCKED</span></section>
<section class='card metric'><small>Initial markets</small><strong>UK · EU · Japan</strong><small>One exchange at a time</small></section><section class='card metric'><small>Benchmarks</small><strong>FTSE · STOXX · Nikkei</strong><small>Local total-return indices</small></section><section class='card metric'><small>Currency</small><strong>Multi-FX</strong><small>Base return reported in INR</small></section><section class='card metric'><small>Paper capital</small><strong>Not started</strong><small>No simulated orders</small></section>
<section class='card checklist'><h2>Before paper activation</h2><ul><li>Exchange-specific membership, holidays and trading hours</li><li>Local currency, dividends and withholding taxes</li><li>Liquidity and data-quality gates for each market</li><li>Separate historical holdout and benchmark comparison</li><li>Separate ledgers so results cannot contaminate phases</li></ul></section><section class='card roadmap'><h2>Promotion rule</h2><p>Each country must pass independently. Markets that fail remain visible as research but cannot place paper orders.</p></section></main>
<p class='warning'>Delayed public data and GitHub schedules are not exchange-grade. Results include estimated costs but not every tax, gap, slippage event or guaranteed fill.</p>
<script>
const health=document.getElementById('schedule-health'), scan=Date.parse(health.dataset.scan);
const india=new Date(Date.now()+330*60000), minutes=india.getUTCHours()*60+india.getUTCMinutes();
const market=india.getUTCDay()>0&&india.getUTCDay()<6&&minutes>=555&&minutes<=930;
const stale=!Number.isFinite(scan)||(Date.now()-scan)>20*60*1000;
health.textContent=market&&stale?'Scan delayed':'Schedule healthy';
health.className=market&&stale?'stale':'safe';
const history={chart_data}, canvas=document.getElementById('performance-chart'), ctx=canvas.getContext('2d');
function draw(days=0){{
 const cutoff=days?Date.now()-days*86400000:0, data=history.filter(x=>Date.parse(x.timestamp)>=cutoff);
 const shown=data.length>1?data:history, ratio=window.devicePixelRatio||1, rect=canvas.getBoundingClientRect();
 canvas.width=rect.width*ratio;canvas.height=255*ratio;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,rect.width,255);
 if(shown.length<2){{ctx.fillStyle='#7a857f';ctx.font='14px system-ui';ctx.fillText('Performance history will appear after more successful scans.',16,120);return}}
 const series=[shown.map(x=>x.equity/shown[0].equity-1),shown.map(x=>x.nifty/shown[0].nifty-1)], all=series.flat(), min=Math.min(...all),max=Math.max(...all),span=max-min||.01;
 ctx.strokeStyle='#e7ebe8';ctx.lineWidth=1;for(let i=0;i<4;i++){{let y=20+i*65;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(rect.width,y);ctx.stroke()}}
 series.forEach((values,index)=>{{ctx.strokeStyle=index?'#9da7a1':'#00a77b';ctx.lineWidth=index?2:3;ctx.beginPath();values.forEach((value,i)=>{{const x=i/(values.length-1)*rect.width,y=230-(value-min)/span*205;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}});ctx.stroke()}});
}}
document.querySelectorAll('.ranges button').forEach(button=>button.onclick=()=>{{document.querySelectorAll('.ranges button').forEach(x=>x.classList.remove('active'));button.classList.add('active');draw(+button.dataset.days)}});addEventListener('resize',()=>draw(+document.querySelector('.ranges .active').dataset.days));draw();
document.querySelectorAll('.markets button').forEach(button=>button.onclick=()=>{{document.querySelectorAll('.markets button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.market-panel').forEach(x=>x.classList.remove('active'));button.classList.add('active');document.getElementById(button.dataset.market).classList.add('active');if(button.dataset.market==='india')draw(+document.querySelector('.ranges .active').dataset.days)}});
</script>
</div></body></html>"""
    PAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAGE_PATH.write_text(page)


def run(force: bool = False) -> dict:
    state = load_state()
    now = datetime.now(UTC)
    state["last_attempt"] = now.isoformat()
    if not trading_enabled():
        state["status"] = "Disabled from GitHub control file; no paper orders"
        state["last_run"] = now.isoformat()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
        render_page(state, {})
        return state
    if not force and not market_is_open(now):
        state["status"] = "Skipped: NSE market is closed"
        state["last_run"] = now.isoformat()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
        render_page(state, {})
        return state

    india_day = now.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
    try:
        index_frame = yahoo_chart("^NSEI", period="3mo", interval="1d").frame
        exposure_target = volatility_target_exposure(index_frame)
    except (OSError, ValueError, TypeError, KeyError, IndexError, requests.RequestException):
        state["status"] = "Skipped: Nifty volatility risk data unavailable"
        state["last_run"] = now.isoformat()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
        render_page(state, {})
        return state
    state["exposure_target"] = exposure_target
    new_session = state.get("last_scan_date") != india_day
    session_count = state.get("sessions_since_review", REVIEW_SESSIONS) + int(new_session)
    review_due = not state["positions"] or session_count >= REVIEW_SESSIONS
    watchlist = json.loads(WATCHLIST_PATH.read_text())
    scan_symbols = watchlist if review_due else list(state["positions"])
    candidates, quotes, latest_data_at = [], {}, None
    for symbol in scan_symbols:
        try:
            frame = yahoo_chart(
                symbol, period="5y" if review_due else "1d",
                interval="1d" if review_due else "5m",
            ).frame
            if not quote_is_current(frame.timestamp.iloc[-1], india_day):
                continue
            price = float(frame.close.iloc[-1])
            quotes[symbol] = price
            timestamp = frame.timestamp.iloc[-1]
            latest_data_at = timestamp if latest_data_at is None else max(latest_data_at, timestamp)
            if review_due:
                score = risk_adjusted_momentum_score(frame)
                if score is not None:
                    candidates.append((score, symbol, price))
        except (OSError, ValueError, TypeError, KeyError, IndexError, requests.RequestException):
            continue

    state["latest_data_at"] = latest_data_at.isoformat() if latest_data_at is not None else None
    insufficient_review = review_due and len(candidates) < 40
    insufficient_monitoring = not review_due and len(quotes) < len(scan_symbols)
    if insufficient_review or insufficient_monitoring:
        if review_due:
            state["status"] = f"Skipped review: only {len(candidates)}/50 valid Nifty quotes"
        else:
            state["status"] = f"Skipped monitoring: only {len(quotes)}/{len(scan_symbols)} current quotes"
        state["last_run"] = now.isoformat()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
        render_page(state, quotes)
        return state

    state["last_scan_date"] = india_day
    state["sessions_since_review"] = session_count

    actions = []
    if state.get("last_corporate_action_date") != india_day:
        for symbol, item in state["positions"].items():
            item.setdefault("opened_at", state.get("last_run") or now.isoformat())
            try:
                actions.extend(yahoo_corporate_actions(symbol))
            except (OSError, ValueError, TypeError, KeyError, requests.RequestException):
                continue
        state["last_corporate_action_date"] = india_day
    action_messages = apply_corporate_actions(state, actions)

    fills = []
    equity = state["cash"] + sum(
        item["quantity"] * quotes.get(symbol, item.get("last_price", item["entry_price"]))
        for symbol, item in state["positions"].items()
    )
    state["peak_equity"] = max(state.get("peak_equity", equity), equity)
    drawdown = equity / state["peak_equity"] - 1
    if state.get("cooldown_until") and not cooldown_active(state, now):
        state["cooldown_until"] = None
        state["peak_equity"] = equity
    ranked = sorted(candidates, reverse=True)
    allowed = {symbol for _, symbol, _ in ranked[:KEEP_RANK]}
    drawdown_stop = drawdown_stop_triggered(drawdown, bool(state["positions"]))
    if drawdown_stop:
        state["cooldown_until"] = (now + timedelta(days=COOLDOWN_DAYS)).isoformat()
    if drawdown_stop or cooldown_active(state, now):
        allowed.clear()

    for symbol in list(state["positions"]):
        item = state["positions"][symbol]
        price = quotes.get(symbol, item.get("last_price", item["entry_price"]))
        if drawdown_stop or cooldown_active(state, now) or (review_due and symbol not in allowed):
            state["cash"], _, fill = execute_paper_fill(
                state["cash"], item["quantity"], symbol=symbol, side="SELL",
                quantity=item["quantity"], price=price, fee_bps=FEE_BPS,
            )
            fills.append(fill)
            del state["positions"][symbol]
    if drawdown_stop:
        state["peak_equity"] = state["cash"]

    invested = sum(
        item["quantity"] * quotes.get(symbol, item.get("last_price", item["entry_price"]))
        for symbol, item in state["positions"].items()
    )
    target_invested = equity * exposure_target
    if invested > target_invested * 1.02:
        keep_fraction = target_invested / invested
        for symbol, item in list(state["positions"].items()):
            quantity = item["quantity"] - int(item["quantity"] * keep_fraction)
            if quantity < 1:
                continue
            price = quotes.get(symbol, item.get("last_price", item["entry_price"]))
            state["cash"], remaining, fill = execute_paper_fill(
                state["cash"], item["quantity"], symbol=symbol, side="SELL",
                quantity=quantity, price=price, fee_bps=FEE_BPS,
            )
            fills.append(fill)
            item["quantity"] = remaining

    if review_due and not cooldown_active(state, now):
        state["sessions_since_review"] = 0
    for _, symbol, price in (ranked if review_due else []):
        if symbol in state["positions"] or len(state["positions"]) >= MAX_POSITIONS:
            continue
        allocation = min(target_invested / MAX_POSITIONS, state["cash"])
        affordable = int(state["cash"] / (price * (1 + FEE_BPS / 10_000)))
        quantity = min(int(allocation / (price * (1 + FEE_BPS / 10_000))), affordable)
        if quantity < 1:
            continue
        state["cash"], _, fill = execute_paper_fill(
            state["cash"], 0, symbol=symbol, side="BUY", quantity=quantity,
            price=price, fee_bps=FEE_BPS,
        )
        fills.append(fill)
        state["positions"][symbol] = {
            "quantity": quantity, "entry_price": price, "last_price": price,
            "opened_at": now.isoformat(),
        }

    # Reinvest corporate-action cash toward equal weights on scheduled reviews.
    if review_due and state["positions"]:
        target_value = target_invested / MAX_POSITIONS
        ranked_prices = {symbol: price for _, symbol, price in ranked}
        for _, symbol, price in ranked:
            item = state["positions"].get(symbol)
            if not item:
                continue
            gap = max(0.0, target_value - item["quantity"] * price)
            quantity = min(
                int(gap / (price * (1 + FEE_BPS / 10_000))),
                int(state["cash"] / (price * (1 + FEE_BPS / 10_000))),
            )
            if quantity < 1:
                continue
            old_quantity, old_cost = item["quantity"], item["quantity"] * item["entry_price"]
            state["cash"], new_quantity, fill = execute_paper_fill(
                state["cash"], old_quantity, symbol=symbol, side="BUY", quantity=quantity,
                price=ranked_prices[symbol], fee_bps=FEE_BPS,
            )
            fills.append(fill)
            item["quantity"] = new_quantity
            item["entry_price"] = (old_cost + quantity * price) / new_quantity

    for symbol, item in state["positions"].items():
        item["last_price"] = quotes.get(symbol, item.get("last_price", item["entry_price"]))
    state["last_equity"] = state["cash"] + sum(
        mark_to_market(0, item["quantity"], item["last_price"])
        for item in state["positions"].values()
    )
    state["last_run"] = now.isoformat()
    state["last_successful_scan"] = now.isoformat()
    record_history(state, now.isoformat(), float(index_frame.close.iloc[-1]))
    action = "60-session review" if review_due else "monitoring existing holdings"
    corporate = f"; {len(action_messages)} corporate action(s)" if action_messages else ""
    state["status"] = (
        f"Completed {action}; {len(fills)} paper fill(s); "
        f"volatility target {exposure_target:.0%}{corporate}"
    )
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))
    append_fills(fills)
    render_page(state, quotes)
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Run outside NSE hours for testing")
    args = parser.parse_args()
    print(json.dumps(run(force=args.force), indent=2))


if __name__ == "__main__":
    main()
