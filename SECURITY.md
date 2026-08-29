# Security

Report vulnerabilities privately to the repository owner. Do not open a public issue containing credentials, account identifiers, positions, or exploit details.

Secrets and IBKR account identifiers must never enter Git, CSV uploads, screenshots, or dashboard logs. Use environment or platform secret storage. Keep the IBKR API bound to a trusted network interface, prefer localhost, restrict trusted IPs, and never forward the API port to the public internet.

The container runs as a non-root user with `no-new-privileges`; the dashboard filesystem is read-only in Compose. Keep dependencies and base images patched, require protected-branch CI, and review release diffs before deployment.

