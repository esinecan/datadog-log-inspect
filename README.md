# Datadog CLI V2

Python-based CLI for querying Datadog **logs** and **RUM** using internal web UI APIs with browser session auth.

## MCP Server

An MCP (Model Context Protocol) server is included for AI assistant integration. The server wraps the dd-cli and exposes the following tools:

### Backend Logs Tools
| Tool | Description |
|------|-------------|
| `dd_auth_status` | Check Datadog authentication status |
| `dd_search_logs` | Search backend logs with Datadog query syntax |
| `dd_trace_logs` | Get all logs for a specific trace_id |
| `dd_fetch_log` | Fetch full details of a single log entry |
| `dd_top_values` | Aggregate top values for any field |

### RUM (Frontend) Tools
| Tool | Description |
|------|-------------|
| `dd_rum_sessions` | Query user sessions by customer ID or email |
| `dd_rum_actions` | Query user actions (clicks, inputs, navigations) |
| `dd_rum_errors` | Query frontend JavaScript errors |
| `dd_rum_resources` | Query network resources (XHR, fetch, assets) |

### MCP Server Setup

```bash
# Build MCP server
cd mcp && npm install && npm run build

# Run with stdio transport
node dist/mcp/server.js

# Configure in Claude Desktop / Cline settings:
# Command: node /path/to/datadog-log-inspect/mcp/dist/mcp/server.js
```

### TODO: Field Discovery API

> **⚠️ The `dd_fields_search` and `dd_fields_values` tools are currently broken (400 errors).**
> 
> The internal API endpoints have changed. Need to:
> 1. Open Datadog web UI and trigger field autocomplete
> 2. Capture the network requests from DevTools
> 3. Reverse engineer the new payload format
> 
> **Workaround**: Use `dd_top_values` with the `field` parameter to discover field values.


## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Make executable
chmod +x dd-cli

# Configure auth (interactive)
./dd-cli auth
```

## Auth Setup

1. Open https://app.datadoghq.eu/logs in Chrome
2. Open DevTools (F12) → Network tab
3. Perform any search
4. Find a request to `logs-analytics`
5. Right-click → Copy as cURL
6. Extract `dogweb` cookie and `x-csrf-token` header

## Commands Overview

```
dd-cli
├── auth / status          # Authentication
├── list / fetch-all       # Backend logs
├── trace / deep / top     # Backend logs analysis
├── rum                    # RUM (Real User Monitoring)
│   ├── sessions           # User sessions
│   ├── actions            # Clicks, inputs
│   ├── views              # Page views
│   ├── errors             # JS errors
│   ├── resources          # XHR/fetch
│   ├── fetch-all          # Stream all
│   └── top                # Aggregate
├── fields                 # Schema exploration
│   ├── search             # Find field names
│   └── values             # Field autocomplete
├── watchdog               # AI anomaly detection
└── views                  # Saved views
```

## Backend Logs

```bash
# List logs
./dd-cli list 'service:pricing status:error' --hours 24 --limit 100

# Stream all logs (NDJSON)
./dd-cli fetch-all 'S1234567' --hours 48 --max 500

# Trace correlation
./dd-cli trace <trace_id> --hours 24

# Deep hydration
./dd-cli deep 'shipment:S1234567' --hours 24 --max 50
```

## RUM (Real User Monitoring)

Query frontend user interactions: sessions, clicks, page views, network requests, JS errors.

```bash
# Find sessions for a customer
./dd-cli rum sessions 'C-13947' --hours 48

# Find user actions matching text
./dd-cli rum actions '"retrieve rates"' --hours 24

# Find JS errors for a user
./dd-cli rum errors '@usr.id:alice@example.com' --limit 50

# Stream all RUM events
./dd-cli rum fetch-all 'C-13947' --max 200 --type action

# Aggregate RUM by event type
./dd-cli rum top '*' --field log_type --hours 24
```

### When to use logs vs RUM?

| Use Case | Command |
|----------|---------|
| Backend service errors | `dd-cli list 'status:error'` |
| Frontend user sessions | `dd-cli rum sessions 'user@email.com'` |
| API trace correlation | `dd-cli trace <trace_id>` |
| Frontend JS crashes | `dd-cli rum errors '*'` |
| Network requests in browser | `dd-cli rum resources '*'` |

## Field Exploration

Discover available fields and their values for building queries.

```bash
# Find fields containing "usr"
./dd-cli fields search 'usr' --source rum

# Get values for @usr.id in RUM
./dd-cli fields values '@usr.id' --source rum --hours 24

# Get values for service in logs
./dd-cli fields values 'service' --source logs
```

## Watchdog AI Insights

Search for AI-detected anomalies.

```bash
./dd-cli watchdog 'status:error' --hours 24
./dd-cli watchdog 'service:pricing' --source logs
```

## Saved Views

List team-shared saved views.

```bash
./dd-cli views list --source logs
./dd-cli views list --search 'pricing' --source rum
```

## Output

- **stdout**: JSON or NDJSON (one JSON object per line)  
- **stderr**: Status messages or errors

```bash
# Pipe to jq for processing
./dd-cli rum fetch-all 'C-13947' --max 100 | jq -c '.event.@action.name'

# Save to file
./dd-cli fetch-all 'S1234567' --max 500 > logs.ndjson
```

## Internal API Endpoints

| Command | Endpoint |
|---------|----------|
| list | `/api/v1/logs-analytics/list?type=logs` |
| rum * | `/api/v1/logs-analytics/*?type=rum` |
| fields search | `/api/ui/event-platform/query/field` |
| fields values | `/api/ui/event-platform/query/field-value` |
| watchdog | `/api/v2/watchdog/insights/search` |
| views | `/api/v1/logs/views` |
