# Datadog Log Inspect

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)

Python-based CLI and MCP server for querying Datadog **logs** and **RUM** (Real User Monitoring) using internal web UI APIs with browser session authentication.

> **Note**: This tool uses reverse-engineered Datadog internal APIs, not official public APIs. It requires browser session authentication.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [MCP Server Integration](#mcp-server-integration)
- [CLI Usage](#cli-usage)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Features

### Backend Log Tools
- 🔍 **Search logs** with Datadog query syntax
- 🔗 **Trace correlation** - get all logs for a trace ID
- 📊 **Aggregations** - top values for any field
- 🎯 **Deep hydration** - fetch full log details

### RUM (Frontend) Tools
- 👥 **User sessions** - track customer journeys
- 🖱️ **User actions** - clicks, inputs, navigation events
- ❌ **JavaScript errors** - frontend crash debugging
- 🌐 **Network resources** - XHR, fetch, asset loading

### AI Assistant Integration
- 🤖 **MCP Server** for Claude Desktop, Cline, and other MCP clients
- 🔌 **Plug-and-play** AI-powered log analysis

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/datadog-log-inspect.git
cd datadog-log-inspect

# Install Python CLI
pip install -e ".[dev]"

# Build MCP server (optional, for AI integration)
cd mcp
npm install
npm run build
```

### Requirements

- **Python**: 3.9 or higher
- **Node.js**: 18 or higher (for MCP server only)
- **Datadog Access**: Valid Datadog account with web UI access

## Quick Start

### 1. Authenticate

```bash
# Interactive auth setup
dd-cli auth
```

Follow the prompts to extract session tokens from your browser:
1. Open https://app.datadoghq.eu/logs in Chrome
2. Open DevTools (F12) → Network tab
3. Perform any search
4. Find a request to `logs-analytics`
5. Right-click → Copy as cURL
6. Extract `dogweb` cookie and `x-csrf-token` header values

### 2. Verify Authentication

```bash
dd-cli status
```

### 3. Query Logs

```bash
# Search recent errors
dd-cli list 'service:my-service status:error' --hours 24 --limit 50

# Get logs for a specific trace
dd-cli trace abc123def456 --hours 24

# Aggregate top services with errors
dd-cli top 'status:error' --field service --hours 24
```

### 4. Query RUM (Frontend Data)

```bash
# Find user sessions
dd-cli rum sessions 'customer@example.com' --hours 48

# Find user actions (clicks, navigation)
dd-cli rum actions '"retrieve rates"' --hours 24

# Find JavaScript errors
dd-cli rum errors '*' --hours 24 --limit 100
```

## MCP Server Integration

The MCP (Model Context Protocol) server enables AI assistants like Claude to query your Datadog logs directly.

### Setup for Claude Desktop

1. **Build the MCP server**:
```bash
cd mcp
npm install
npm run build
```

2. **Configure Claude Desktop**:

Edit your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "datadog": {
      "command": "node",
      "args": [
        "/ABSOLUTE/PATH/TO/datadog-log-inspect/mcp/dist/mcp/server.js"
      ]
    }
  }
}
```

3. **Restart Claude Desktop**

4. **Verify**: Ask Claude "What MCP tools do you have?" - you should see datadog tools listed.

### Setup for Cline (VSCode)

See [`examples/cline-mcp-config.json`](examples/cline-mcp-config.json) for configuration.

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `dd_auth_status` | Check authentication status |
| `dd_search_logs` | Search backend logs |
| `dd_trace_logs` | Get all logs for a trace ID |
| `dd_fetch_log` | Fetch full details of a log entry |
| `dd_top_values` | Aggregate top values for any field |
| `dd_rum_sessions` | Query user sessions |
| `dd_rum_actions` | Query user actions |
| `dd_rum_errors` | Query JavaScript errors |
| `dd_rum_resources` | Query network resources |

## CLI Usage

### Commands Overview

```
dd-cli
├── auth / status          # Authentication
├── list / fetch-all       # Backend logs search
├── trace / deep / top     # Backend logs analysis
├── rum                    # RUM (Real User Monitoring)
│   ├── sessions           # User sessions
│   ├── actions            # User clicks/inputs
│   ├── views              # Page views
│   ├── errors             # JS errors
│   ├── resources          # Network requests
│   ├── fetch-all          # Stream all events
│   └── top                # Aggregate RUM data
├── watchdog               # AI anomaly detection
└── views                  # List saved views
```

### Examples

```bash
# Backend Logs
dd-cli list 'service:pricing status:error' --hours 24 --limit 100
dd-cli fetch-all 'shipment:S1234567' --hours 48 --max 500 > logs.ndjson
dd-cli trace abc123def456 --hours 24
dd-cli top 'status:error' --field service --hours 24

# RUM (Frontend)
dd-cli rum sessions 'customer@example.com' --hours 48
dd-cli rum actions '"search button"' --hours 24
dd-cli rum errors '@usr.id:alice@example.com' --limit 50
dd-cli rum resources '*' --hours 24 --limit 100

# Analysis
dd-cli watchdog 'service:my-service' --hours 24
dd-cli views list --source logs
```

### Output Format

- **stdout**: JSON or NDJSON (newline-delimited JSON)
- **stderr**: Status messages and errors

```bash
# Pipe to jq for processing
dd-cli rum sessions 'C-12345' | jq -r '.event."@usr.email"'

# Save to file
dd-cli fetch-all 'S1234567' --max 500 > shipment_logs.ndjson
```

## Security

### Token Storage

Authentication tokens are stored in `~/.datadog-auth` with **0600 permissions** (owner read/write only).

```bash
# Check your auth file permissions
ls -la ~/.datadog-auth
# Should show: -rw------- (only owner can read/write)
```

### Token Lifecycle

- Tokens are **browser session cookies** tied to your Datadog login
- Tokens expire when you log out of Datadog web UI or after session timeout
- **No automatic refresh** - you must re-run `dd-cli auth` when tokens expire
- Tool will show `401 Unauthorized` when tokens are invalid

### Best Practices

✅ **Do**:
- Re-authenticate regularly (tokens expire)
- Keep `~/.datadog-auth` private (never commit to git)
- Use in secure environments only

❌ **Don't**:
- Share your `~/.datadog-auth` file
- Commit tokens to version control
- Use on shared/untrusted systems

## Troubleshooting

### "No auth found" Error

```bash
# Run interactive auth setup
dd-cli auth

# Verify it worked
dd-cli status
```

### 401/403 Errors

Your session tokens have expired. Re-authenticate:

```bash
dd-cli auth
```

### "dd-cli: command not found"

Ensure the package is installed and in your PATH:

```bash
# If installed with pip
which dd-cli

# If running from source
./dd-cli --help
```

### MCP Server Not Appearing

1. Check the server builds successfully:
```bash
cd mcp
npm run build
```

2. Verify the path in your MCP config is absolute and correct

3. Check MCP server logs in Claude Desktop debug console

4. Test with MCP inspector:
```bash
cd mcp
npm run inspector
```

### Wrong Datadog Region

If you're not on EU region (`app.datadoghq.eu`), configure your base URL:

Edit `~/.datadog-auth` and add:
```bash
DD_BASE_URL="https://app.datadoghq.com"  # US1
# or
DD_BASE_URL="https://us3.datadoghq.com"  # US3
```

## Documentation

- [**ARCHITECTURE.md**](ARCHITECTURE.md) - Technical architecture and how it works
- [**CONTRIBUTING.md**](CONTRIBUTING.md) - Contributing guidelines
- [**CHANGELOG.md**](CHANGELOG.md) - Version history
- [**examples/**](examples/) - Configuration examples for MCP clients

## Known Limitations

- Requires browser session authentication (not official API keys)
- Subject to Datadog internal API changes without notice
- No streaming for large result sets (loads into memory)
- Tokens expire and require manual refresh
- Rate limited by Datadog's internal limits

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built by reverse engineering Datadog's internal web UI APIs for better log analysis and AI integration.

**Disclaimer**: This is an unofficial tool and is not affiliated with or endorsed by Datadog, Inc.
