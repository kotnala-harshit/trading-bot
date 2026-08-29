# Start here

## 1. Verify locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev,ibkr]'
./scripts/preflight.sh
streamlit run app.py
```

The default dashboard uses safe paper configuration and synthetic sample data.

## 2. Push to a private GitHub repository

Create an empty private repository on GitHub without a generated README. Then, from this folder:

```bash
git init
git add .
git commit -m "Initial production-safe quant workbench"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_PRIVATE_REPO.git
git push -u origin main
```

In GitHub, confirm **Settings → General → Danger Zone → Change repository visibility** says Private. Add branch protection for `main`, requiring the `test` and `docker` checks from CI. Never commit `.env`, `secrets.toml`, credentials, account IDs, or purchased market data.

## 3. Deploy the dashboard on Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> using GitHub.
2. Authorize access to the selected private repository.
3. Choose the repository and `main` branch.
4. Set the app file to `app.py`, then deploy.

No secrets are required for the read-only dashboard. Streamlit Community Cloud cannot reach TWS or IB Gateway running on your Mac through `127.0.0.1`; therefore IBKR connectivity and runtime execution belong on the machine or private server where Gateway runs. Do not expose an IBKR API port publicly.

## 4. Run paper/staging locally with Docker

```bash
./scripts/deploy_paper.sh
docker compose -f deploy/docker-compose.prod.yml ps
```

The dashboard is at <http://localhost:8501>. The runtime writes `runtime/heartbeat.json`. Stop it with `./scripts/stop_production.sh`.

## 5. Connect IBKR paper

Run TWS paper trading on port 7497, or IB Gateway paper on 4002, and allow local API clients. Match the port in the selected config, then run:

```bash
qts doctor --config configs/production-paper.yaml --require-ibkr
```

This tests TCP reachability only. It does not authenticate, confirm subscriptions, inspect the account, or send an order.

