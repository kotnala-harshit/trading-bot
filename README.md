# Quant Trading Workbench

A single, deployable MES research and operational-readiness project. It includes an upload-driven Streamlit dashboard, deterministic moving-average research baseline, OHLCV validation, cost stress, IBKR endpoint diagnostics, Docker services, CI, and hard live-trading interlocks.

The hosted app is organized as a broader Money Workspace. Indian cash equities are Phase 1, US equities are Phase 2, and other global markets are Phase 3. The Indian lab includes delayed-live data, a transparent trend baseline, a historical development-versus-forward comparison, and a session-only paper portfolio that cannot transmit broker orders. MES futures and RoyaltyIQ remain future modules.

> The bundled CSV is synthetic. It validates the software path, not a trading edge. The dashboard never places orders. Live autonomous transmission is disabled in the committed configuration.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,ibkr]'
pytest -q
streamlit run app.py
```

Open <http://localhost:8501>. For the full private GitHub, Streamlit Community Cloud, Docker, and IBKR setup, see [START_HERE.md](START_HERE.md).

## Safety boundary

This repository is production-shaped for paper/staging operations. It is not certified as profitable, fault-tolerant, or suitable for unattended real-money trading. Live promotion requires a deliberate config change plus four runtime acknowledgements; it also requires completing the evidence checklist in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).
