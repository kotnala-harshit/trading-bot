# Operations runbook

## Start and observe

```bash
./scripts/preflight.sh
./scripts/deploy_paper.sh
docker compose -f deploy/docker-compose.prod.yml ps
docker compose -f deploy/docker-compose.prod.yml logs -f
```

Healthy means the dashboard health check passes, `runtime/heartbeat.json` advances, the selected mode is PAPER, and broker diagnostics match the intended paper endpoint.

## Stop

```bash
./scripts/stop_production.sh
```

If any unexpected order, position, stale feed, repeated reconnect, daily-loss breach, or config mismatch occurs: stop the runtime, use TWS/Gateway to cancel open orders, independently verify positions, and follow the broker-approved flatten procedure. Do not rely on this software as the only control plane.

## Recovery

Before restarting, capture logs, confirm the incident cause, verify broker orders and positions independently, rotate any exposed secret, and rerun preflight. Restart in dry-run or paper mode. Record timestamp, operator, release, config hash, broker state, and decision.

