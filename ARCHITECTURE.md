# Architecture

## Overview

`datadog-log-inspect` is a reverse-engineered client for Datadog's internal web UI APIs. It provides both a CLI and an MCP (Model Context Protocol) server for querying logs and RUM data.

## How It Works

### Authentication

Instead of using Datadog's official API keys, this tool uses **browser session authentication**:

1. User logs into Datadog web UI in their browser
2. User extracts session cookies and CSRF token from browser DevTools
3. Tokens are stored locally in `~/.datadog-auth` (0600 permissions)
4. All API requests include these browser session credentials

**Why browser auth?**
- Access to internal APIs not available via official API
- Some features (like RUM queries) require web UI session
- No need for separate API key management

### Python CLI Layer

**Components:**
- `dd_cli/client.py`: Core `DatadogWebLogs` client wrapping HTTP requests
- `dd_cli/cli.py`: Argparse-based CLI with subcommands
- `dd_cli/auth.py`: Token storage and loading
- `dd_cli/profiles.py`: Column profile presets for different log views

**Request Flow:**
```
CLI Command → DatadogWebLogs.method() → HTTP POST to Datadog API → Parse JSON → Output NDJSON
```

### TypeScript MCP Server

**Components:**
- `mcp/src/mcp/server.ts`: MCP protocol server using `@modelcontextprotocol/sdk`
- `mcp/src/core/executor.ts`: Spawns Python `dd-cli` subprocess and captures output
- `mcp/src/tools/index.ts`: Tool definitions exposed to MCP clients

**Request Flow:**
```
AI Assistant → MCP Tool Call → executor.ts spawns dd-cli → Parse stdout → Return to AI
```

The MCP server is a **thin wrapper** around the Python CLI - it doesn't reimplement the logic, just exposes it via MCP protocol.

## API Endpoints Used

All endpoints are internal Datadog web UI APIs (not official public APIs):

| Endpoint | Purpose |
|----------|---------|
| `/api/v1/logs-analytics/list?type=logs` | Backend log search |
| `/api/v1/logs-analytics/list?type=rum` | RUM event queries |
| `/api/v1/logs-analytics/aggregate?type=logs` | Log aggregations (top values) |
| `/api/v2/watchdog/insights/search` | Watchdog AI insights |
| `/api/v1/logs/views` | Saved views list |

**Request Format:**
```json
{
  "query": "service:my-service status:error",
  "from": 1704067200000,
  "to": 1704153600000,
  "sort": "desc",
  "options": {
    "timezone": "UTC"
  },
  "columns": [
    {"field": {"path": "timestamp"}},
    {"field": {"path": "service"}},
    {"field": {"path": "message"}}
  ],
  "limit": 100
}
```

## Data Flow

### Example: Searching Logs via MCP

```
┌─────────────┐
│ AI Assistant│
│ (Claude)    │
└──────┬──────┘
       │ MCP: dd_search_logs(query, hours)
       ▼
┌──────────────────┐
│ MCP Server (TS)  │
│ server.ts        │
└────────┬─────────┘
         │ spawn: dd-cli list 'query' --hours 24
         ▼
┌──────────────────┐
│ Python dd-cli    │
│ client.py        │
└────────┬─────────┘
         │ POST /api/v1/logs-analytics/list
         │ Headers: Cookie, x-csrf-token
         ▼
┌──────────────────┐
│ Datadog API      │
│ (app.datadoghq.eu)│
└────────┬─────────┘
         │ JSON Response
         ▼
┌──────────────────┐
│ Parse & Format   │
│ → NDJSON output  │
└────────┬─────────┘
         │
         ▼
     AI gets structured log data
```

## Security Considerations

### Token Storage
- Stored in `~/.datadog-auth` with **0600 permissions** (owner read/write only)
- Plain text format (not encrypted)
- Same security model as `~/.aws/credentials` or `~/.kube/config`

### Token Lifecycle
- Tokens are **browser session cookies** that expire
- No automatic refresh - user must manually re-authenticate
- Tool detects 401/403 and prompts re-auth

### Network Security
- All requests to `https://app.datadoghq.eu` (or configured base URL)
- Uses system's trusted CA certificates
- No proxy support currently

## Extension Points

### Adding New Commands

1. **Python CLI**: Add method to `DatadogWebLogs` class
2. **CLI**: Add subcommand in `cli.py`
3. **MCP**: Add tool definition in `mcp/src/tools/index.ts`

### Custom Column Profiles

Edit `dd_cli/profiles.py`:
```python
PROFILES["my-profile"] = [
    {"field": {"path": "timestamp"}},
    {"field": {"path": "custom_field"}},
]
```

### Supporting Other Datadog Regions

Set `DD_BASE_URL` in `~/.datadog-auth`:
```bash
DD_BASE_URL="https://app.datadoghq.com"  # US1
DD_BASE_URL="https://us3.datadoghq.com"  # US3
```

## Limitations

- **Browser session dependency**: Tokens expire with browser logout
- **Internal API changes**: Datadog can break compatibility anytime
- **No streaming**: Large result sets loaded into memory
- **Rate limiting**: Subject to Datadog's internal rate limits
