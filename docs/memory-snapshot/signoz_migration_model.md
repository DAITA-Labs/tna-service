---
name: SigNoz migration model post-0.113
description: SigNoz v0.113.0 (2026-02-25) deprecated signoz-schema-migrator; migration commands now live inside signoz-otel-collector binary
type: reference
originSessionId: 659793e3-6c58-46b7-bff9-b72ea49f6602
---
**Fact:** Starting SigNoz v0.113.0 (released 2026-02-25), the separate `signoz/signoz-schema-migrator` image is deprecated. ClickHouse schema migration (creating `signoz_traces`, `signoz_metrics`, `signoz_logs` databases and their tables) is now performed by the `signoz/signoz-otel-collector` binary itself via subcommands:
- `signoz-otel-collector migrate bootstrap`
- `signoz-otel-collector migrate sync up`
- `signoz-otel-collector migrate async up`

The component is called `signoz-telemetrystore-migrator` in SigNoz's reference compose. It runs as a one-shot service using the same `signoz/signoz-otel-collector` image with a different `command:`. The main otel-collector also runs `migrate sync check` at startup and waits on ClickHouse-based readiness instead of a Kubernetes Job.

**Why:** Removes startup-ordering issues of the old separate-job pattern. Single image, fewer moving parts.

**How to apply:**
- For new SigNoz deployments (docker-compose or Helm), use `signoz-otel-collector` >= 0.113.x and the integrated migrator pattern. Do NOT use `signoz/signoz-schema-migrator:*` (deprecated).
- When the SigNoz docker-compose in this repo (`F:\DAITA\ARENA\TNA\tna-service\docker-compose.yml`) is upgraded past 0.111.7, replace any schema-migrator references with a `signoz-telemetrystore-migrator-sync` one-shot service using `signoz/signoz-otel-collector:<version>` and `command: ["--config=/etc/otelcol/config.yml", "migrate", "sync", "up"]` (verify exact flags against SigNoz's reference compose at https://github.com/SigNoz/signoz/blob/main/deploy/docker/clickhouse-setup/docker-compose.yaml).
- Reference: https://signoz.io/changelog/2026-02-25--breaking-change-new-migration-component-replaces-signoz-schema-migrator-jf8y4e6rnpt9b8pobd01yfun/
- Upgrade guide: https://signoz.io/docs/operate/migration/upgrade-0.113
