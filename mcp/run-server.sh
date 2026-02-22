#!/usr/bin/env bash
# Wrapper for mcp-inspector and MCP client configs.
# Ensures the Python venv and PYTHONPATH are set before launching the Node server.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

export PYTHONPATH="$REPO_ROOT"
export PATH="$REPO_ROOT/venv/bin:$PATH"

exec node "$SCRIPT_DIR/dist/mcp/server.js" "$@"
