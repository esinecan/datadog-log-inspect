"""
Datadog MCP Server

Provides MCP tools for querying Datadog logs and RUM data.
Wraps the dd-cli client library for structured access.
"""

import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Add datadog-log-inspect to path for importing dd_cli
DD_CLI_PATH = Path(__file__).parent.parent.parent.parent / "datadog-log-inspect"
if DD_CLI_PATH.exists():
    sys.path.insert(0, str(DD_CLI_PATH))

from dd_cli.auth import load_auth, get_auth_file_path
from dd_cli.client import DatadogWebLogs, DataSource, RumEventType


# Initialize MCP server
mcp = FastMCP(
    "datadog",
    instructions="Query Datadog logs and RUM data for debugging and observability"
)


def _get_client() -> tuple[Optional[DatadogWebLogs], Optional[dict]]:
    """Get authenticated Datadog client or error dict."""
    auth = load_auth()
    if not auth:
        return None, {
            "error": "Auth not configured",
            "action": f"Run: dd-cli auth (tokens stored at {get_auth_file_path()})"
        }
    return DatadogWebLogs(auth), None


def _simplify_logs(result: dict) -> dict:
    """Extract essential fields from log results for readability."""
    events = result.get("result", {}).get("events", [])
    simplified = []
    for e in events:
        event = e.get("event", {})
        simplified.append({
            "timestamp": event.get("timestamp"),
            "service": event.get("service"),
            "status": event.get("status"),
            "message": event.get("message", "")[:500],  # Truncate long messages
            "trace_id": event.get("trace_id"),
            "id": event.get("id"),
        })
    return {
        "count": len(simplified),
        "events": simplified,
    }


# =============================================================================
# LOG TOOLS
# =============================================================================

@mcp.tool()
def dd_search_logs(
    query: str,
    hours: float = 24,
    limit: int = 50,
    simplified: bool = True
) -> dict:
    """
    Search Datadog backend logs.
    
    Use for:
    - Finding errors: query='service:pricing status:error'
    - Shipment logs: query='S1234567'
    - Service debugging: query='service:rates-management-core status:error'
    - Trace correlation: query='trace_id:abc123'
    
    Args:
        query: Datadog search query (same syntax as web UI)
        hours: Hours back to search (default: 24)
        limit: Max results to return (default: 50)
        simplified: Return simplified output (default: True)
    """
    client, error = _get_client()
    if error:
        return error
    
    result = client.list_logs(query, hours, limit)
    return _simplify_logs(result) if simplified else result


@mcp.tool()
def dd_trace_logs(
    trace_id: str,
    hours: float = 24,
    limit: int = 200,
    simplified: bool = True
) -> dict:
    """
    Get all logs for a specific trace_id.
    
    Use to follow a request across multiple services:
    - Input: trace_id from an error log
    - Output: All related logs showing the full request flow
    
    Args:
        trace_id: The trace ID to search for
        hours: Hours back to search (default: 24)
        limit: Max logs to return (default: 200)
        simplified: Return simplified output (default: True)
    """
    client, error = _get_client()
    if error:
        return error
    
    result = client.trace_logs(trace_id, hours, limit)
    return _simplify_logs(result) if simplified else result


@mcp.tool()
def dd_fetch_log(log_id: str) -> dict:
    """
    Fetch full details of a single log entry.
    
    Use when you need the complete log payload including all fields.
    Get the log_id from dd_search_logs results.
    
    Args:
        log_id: The log ID from a previous search result
    """
    client, error = _get_client()
    if error:
        return error
    
    return client.fetch_one(log_id)


@mcp.tool()
def dd_top_values(
    query: str,
    field: str = "service",
    hours: float = 24,
    limit: int = 10
) -> dict:
    """
    Aggregate top values for a field in matching logs.
    
    Use for:
    - Finding which services have errors: query='status:error', field='service'
    - Distribution by status: query='service:pricing', field='status'
    
    Args:
        query: Datadog search query
        field: Field to aggregate (default: 'service')
        hours: Hours back to search (default: 24)
        limit: Top N values to return (default: 10)
    """
    client, error = _get_client()
    if error:
        return error
    
    return client.aggregate(query, hours, field, limit)


# =============================================================================
# RUM TOOLS
# =============================================================================

def _simplify_rum(result: dict) -> dict:
    """Extract essential fields from RUM results."""
    events = result.get("result", {}).get("events", [])
    simplified = []
    for e in events:
        event = e.get("event", {})
        simplified.append({
            "timestamp": event.get("timestamp"),
            "type": event.get("@type"),
            "session_id": event.get("@session.id"),
            "user_id": event.get("@usr.id"),
            "view_name": event.get("@view.name"),
            "action_name": event.get("@action.name"),
            "error_message": event.get("@error.message"),
        })
    return {
        "count": len(simplified),
        "events": simplified,
    }


@mcp.tool()
def dd_rum_sessions(
    query: str,
    hours: float = 48,
    limit: int = 50,
    simplified: bool = True
) -> dict:
    """
    Query RUM user sessions.
    
    Use for:
    - Finding user activity: query='alice@example.com'
    - Customer sessions: query='C-13947' (customer ID)
    
    Args:
        query: Search query (user email, customer ID, etc.)
        hours: Hours back to search (default: 48)
        limit: Max results (default: 50)
        simplified: Return simplified output (default: True)
    """
    client, error = _get_client()
    if error:
        return error
    
    result = client.rum_sessions(query, hours, limit)
    return _simplify_rum(result) if simplified else result


@mcp.tool()
def dd_rum_actions(
    query: str,
    hours: float = 24,
    limit: int = 50,
    simplified: bool = True
) -> dict:
    """
    Query RUM user actions (clicks, inputs, navigations).
    
    Use for:
    - Finding button clicks: query='"retrieve rates"'
    - User workflows: query='@usr.id:alice@example.com'
    
    Args:
        query: Search query
        hours: Hours back to search (default: 24)
        limit: Max results (default: 50)
        simplified: Return simplified output (default: True)
    """
    client, error = _get_client()
    if error:
        return error
    
    result = client.rum_actions(query, hours, limit)
    return _simplify_rum(result) if simplified else result


@mcp.tool()
def dd_rum_errors(
    query: str,
    hours: float = 24,
    limit: int = 50,
    simplified: bool = True
) -> dict:
    """
    Query RUM frontend JavaScript errors.
    
    Use for:
    - Finding JS crashes: query='*'
    - User-specific errors: query='@usr.id:alice@example.com'
    
    Args:
        query: Search query
        hours: Hours back to search (default: 24)
        limit: Max results (default: 50)
        simplified: Return simplified output (default: True)
    """
    client, error = _get_client()
    if error:
        return error
    
    result = client.rum_errors(query, hours, limit)
    return _simplify_rum(result) if simplified else result


@mcp.tool()
def dd_rum_views(
    query: str,
    hours: float = 24,
    limit: int = 50,
    simplified: bool = True
) -> dict:
    """
    Query RUM page views.
    
    Use for:
    - Finding page visits: query='@view.name:"/quotes"'
    - User navigation: query='@usr.id:alice@example.com'
    
    Args:
        query: Search query
        hours: Hours back to search (default: 24)
        limit: Max results (default: 50)
        simplified: Return simplified output (default: True)
    """
    client, error = _get_client()
    if error:
        return error
    
    result = client.rum_views(query, hours, limit)
    return _simplify_rum(result) if simplified else result


# =============================================================================
# DISCOVERY & META TOOLS
# =============================================================================

@mcp.tool()
def dd_search_fields(
    keyword: str,
    source: str = "logs"
) -> dict:
    """
    Search for available field names in Datadog.
    
    Use to discover what fields you can query on.
    
    Args:
        keyword: Partial field name (e.g., 'usr' finds @usr.id, @usr.email)
        source: Data source - 'logs' or 'rum' (default: 'logs')
    """
    client, error = _get_client()
    if error:
        return error
    
    ds = DataSource.RUM if source == "rum" else DataSource.LOGS
    return client.search_fields(keyword, ds)


@mcp.tool()
def dd_field_values(
    field: str,
    query: str = "*",
    source: str = "logs",
    hours: float = 24
) -> dict:
    """
    Get possible values for a field (autocomplete).
    
    Use to discover what values exist for a field.
    
    Args:
        field: Field path (e.g., '@usr.id', 'service', 'status')
        query: Optional filter query (default: '*')
        source: Data source - 'logs' or 'rum' (default: 'logs')
        hours: Hours back to search (default: 24)
    """
    client, error = _get_client()
    if error:
        return error
    
    ds = DataSource.RUM if source == "rum" else DataSource.LOGS
    return client.field_values(field, query, ds, hours)


@mcp.tool()
def dd_auth_status() -> dict:
    """
    Check Datadog authentication status.
    
    Use to verify if auth tokens are configured and valid.
    Returns auth file location and token age.
    """
    auth = load_auth()
    
    if not auth:
        return {
            "status": "not_configured",
            "auth_file": str(get_auth_file_path()),
            "action": "Run: dd-cli auth"
        }
    
    result = {
        "status": "configured",
        "auth_file": str(get_auth_file_path()),
        "base_url": auth.base_url,
        "cookie_length": len(auth.dogweb_cookie),
        "csrf_token_prefix": auth.csrf_token[:20] + "...",
    }
    
    if auth.created_at:
        from datetime import datetime
        now = datetime.now()
        created = auth.created_at
        if created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        age = now - created
        result["token_age"] = f"{age.days}d {age.seconds // 3600}h"
    
    # Test connection
    client = DatadogWebLogs(auth)
    if client.test_connection():
        result["connection"] = "ok"
    else:
        result["connection"] = "failed"
        result["action"] = "Tokens may be expired. Run: dd-cli auth"
    
    return result


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
