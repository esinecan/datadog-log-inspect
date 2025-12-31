---
description: Accessing Datadog logs for debugging using the Datadog CLI tool
---

# 📊 Datadog Log Access

## Prerequisites
- Custom Datadog CLI script: `.agent/tools/datadog-cli.sh`
- Authenticated via browser token extraction (see `./datadog-cli.sh auth`)

## Quick Access

### Check Status & Authenticate
```bash
# Check if auth is valid
./.agent/tools/datadog-cli.sh status

# Setup auth (interactive - extracts tokens from browser DevTools)
./.agent/tools/datadog-cli.sh auth
```

### Basic Log Query

```bash
# Search logs for a specific shipment (last 1 hour, 50 results)
./.agent/tools/datadog-cli.sh search 'S1124801' 1 50

# Search with service filter (last 24 hours)
./.agent/tools/datadog-cli.sh search 'service:pricing S1124801' 24 100

# Search errors only (last 24 hours)
./.agent/tools/datadog-cli.sh search 'service:rates-management-core status:error' 24 50
```

### Raw JSON Query (for programmatic processing)

```bash
# Get raw JSON response
./.agent/tools/datadog-cli.sh query 'S1124801' 24 100

# Pipe to jq for analysis
./.agent/tools/datadog-cli.sh query 'S1124801' 1 100 | jq '.result.events[] | {timestamp, service, message}'
```

---

## Workflow for Issue Triage

```
1. Read JIRA issue → extract shipment ID, RUM session, app version
2. Run: ./.agent/tools/datadog-cli.sh search '<shipment_id>' 24 100
3. Narrow down with service filters if too many results
4. Look for errors and trace IDs in the output
5. Follow trace IDs across services for full request flow
```

---

## Trace Correlation

When logs have `trace_id`, use it to see request flow across services:

```bash
# Find all logs for a specific trace
./.agent/tools/datadog-cli.sh trace <trace_id> 24
```

---

## Common Queries

| Purpose | Query |
|---------|-------|
| Shipment errors | `<shipment_id> status:error` |
| Rate issues | `service:rates-management-core "RATE_NOT_FOUND"` |
| Revenue service | `service:revenue <shipment_id>` |
| Costs service | `service:costs <shipment_id>` |
| By environment | `env:production service:<service> status:error` |
| Pricing flows | `service:pricing <shipment_id>` |

---

## CLI Commands Reference

| Command | Description |
|---------|-------------|
| `auth` | Setup authentication (interactive, extracts browser tokens) |
| `status` | Check auth status and test connection |
| `query <q> [h] [n]` | Raw JSON query (hours back, limit) |
| `search <q> [h] [n]` | Search and format as text |
| `trace <id> [h]` | Get all logs for a trace_id |

---

## Common Time Ranges

Use hours as second argument:
- `1` - Last hour
- `24` - Last day  
- `168` - Last week
- `360` - Last 15 days

---

## Token Expiry & Re-authentication

Tokens expire periodically. When you see connection failures:

```bash
# Check status
./.agent/tools/datadog-cli.sh status

# If expired, re-authenticate:
./.agent/tools/datadog-cli.sh auth
```

**To get new tokens:**
1. Open https://app.datadoghq.eu/logs in Chrome
2. Open DevTools (F12) → Network tab
3. Perform any search
4. Find a request to 'logs-analytics'
5. Right-click → Copy as cURL
6. Extract `dogweb` cookie and `x-csrf-token` header

---

## Fallback: kubectl (for current pod logs only)

If logs are too old or Datadog is unavailable:

```bash
# Get pod logs (only within pod lifetime)
kubectl logs -n <namespace> --tail=3000 --since=1h --selector=app=<service> | grep "<search_term>"
```

---

## Limitations

| Limitation | Workaround |
|------------|------------|
| Historical logs archived (>7 days) | Use Datadog "Rehydrate from Archives" |
| ~18-40% logs have trace_id | Only APM-traced services have trace IDs |
| Large result sets | Use specific time ranges and service filters |
| Token expiry | Re-run `./datadog-cli.sh auth` |
