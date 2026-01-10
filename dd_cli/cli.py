#!/usr/bin/env python3
"""
Datadog CLI V2 - Query Datadog logs and RUM using internal web UI APIs.

Usage:
    # Backend Logs
    dd-cli list 'service:pricing status:error' --hours 24 --limit 100
    dd-cli fetch-all 'S1234567' --hours 48 --max 500
    dd-cli trace <trace_id> --hours 24
    
    # RUM (Real User Monitoring)  
    dd-cli rum sessions 'C-13947' --hours 48
    dd-cli rum actions '"retrieve rates"' --hours 24
    dd-cli rum errors '@usr.id:alice@example.com' --limit 50
    
    # Field Exploration
    dd-cli fields search 'usr' --source rum
    dd-cli fields values '@usr.id' --source rum
    
    # Watchdog & Views
    dd-cli watchdog 'status:error' --hours 24
    dd-cli views list --source logs
    
    # Auth
    dd-cli auth
    dd-cli status
"""

import argparse
import json
import sys
from datetime import datetime, timedelta

from .auth import load_auth, interactive_auth_setup, get_auth_file_path
from .client import DatadogWebLogs, DataSource, RumEventType
from .profiles import list_profiles


def require_auth() -> DatadogWebLogs:
    """Load auth and create client, or exit with error."""
    auth = load_auth()
    if not auth:
        print("No auth found. Run: dd-cli auth", file=sys.stderr)
        sys.exit(1)
    return DatadogWebLogs(auth)


def emit_json(obj, compact: bool = True):
    """Emit JSON to stdout."""
    if compact:
        print(json.dumps(obj, separators=(",", ":")))
    else:
        print(json.dumps(obj, indent=2))


# =============================================================================
# Command Handlers
# =============================================================================

def cmd_auth(args):
    """Interactive auth setup."""
    interactive_auth_setup()


def cmd_status(args):
    """Check auth status and test connection."""
    auth = load_auth()
    
    if not auth:
        print("✗ No auth file found", file=sys.stderr)
        print(f"  Run: dd-cli auth", file=sys.stderr)
        sys.exit(1)
    
    print(f"Auth file: {get_auth_file_path()}", file=sys.stderr)
    print(f"Cookie length: {len(auth.dogweb_cookie)} chars", file=sys.stderr)
    print(f"CSRF token: {auth.csrf_token[:20]}...", file=sys.stderr)
    
    if auth.created_at:
        # Handle both naive and aware datetimes
        now = datetime.now()
        created = auth.created_at
        if created.tzinfo is not None:
            created = created.replace(tzinfo=None)
        age = now - created
        print(f"Token age: {age.days}d {age.seconds // 3600}h", file=sys.stderr)
    
    print("\nTesting connection...", file=sys.stderr)
    client = DatadogWebLogs(auth)
    
    if client.test_connection():
        print("✓ Connection successful", file=sys.stderr)
    else:
        print("✗ Connection failed - tokens may be expired", file=sys.stderr)
        print("  Run: dd-cli auth", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List logs matching query."""
    client = require_auth()
    result = client.list_logs(
        query=args.query,
        hours=args.hours,
        limit=args.limit,
        profile=args.profile,
    )
    emit_json(result, compact=not args.pretty)


def cmd_fetch_one(args):
    """Fetch full details of a single log."""
    client = require_auth()
    result = client.fetch_one(args.log_id)
    emit_json(result, compact=not args.pretty)


def cmd_fetch_all(args):
    """Stream all logs matching query (NDJSON)."""
    client = require_auth()
    
    count = 0
    for event in client.fetch_all(
        query=args.query,
        hours=args.hours,
        max_logs=args.max,
        profile=args.profile,
    ):
        emit_json(event)
        count += 1
    
    print(f"Fetched {count} logs", file=sys.stderr)


def cmd_deep(args):
    """Fetch logs with full hydration (list + fetch_one)."""
    client = require_auth()
    
    count = 0
    for enriched in client.deep_fetch(
        query=args.query,
        hours=args.hours,
        max_logs=args.max,
        concurrency=args.concurrency,
        profile=args.profile,
    ):
        emit_json(enriched)
        count += 1
    
    print(f"Deep-fetched {count} logs", file=sys.stderr)


def cmd_top(args):
    """Aggregate top values for a field."""
    client = require_auth()
    result = client.aggregate(
        query=args.query,
        hours=args.hours,
        field=args.field,
        limit=args.limit,
    )
    emit_json(result, compact=not args.pretty)


def cmd_facet_info(args):
    """Get facet metadata/stats."""
    client = require_auth()
    result = client.facet_info(
        query=args.query,
        hours=args.hours,
        facet=args.facet,
        limit=args.limit,
    )
    emit_json(result, compact=not args.pretty)


def cmd_trace(args):
    """Find all logs for a trace_id."""
    client = require_auth()
    result = client.trace_logs(
        trace_id=args.trace_id,
        hours=args.hours,
        limit=args.limit,
    )
    emit_json(result, compact=not args.pretty)


# =============================================================================
# RUM Command Handlers
# =============================================================================

def cmd_rum_sessions(args):
    """Query RUM sessions."""
    client = require_auth()
    result = client.rum_sessions(args.query, args.hours, args.limit)
    emit_json(result, compact=not args.pretty)


def cmd_rum_actions(args):
    """Query RUM actions."""
    client = require_auth()
    result = client.rum_actions(args.query, args.hours, args.limit)
    emit_json(result, compact=not args.pretty)


def cmd_rum_views(args):
    """Query RUM page views."""
    client = require_auth()
    result = client.rum_views(args.query, args.hours, args.limit)
    emit_json(result, compact=not args.pretty)


def cmd_rum_errors(args):
    """Query RUM frontend errors."""
    client = require_auth()
    result = client.rum_errors(args.query, args.hours, args.limit)
    emit_json(result, compact=not args.pretty)


def cmd_rum_resources(args):
    """Query RUM network resources."""
    client = require_auth()
    result = client.rum_resources(args.query, args.hours, args.limit)
    emit_json(result, compact=not args.pretty)


def cmd_rum_fetch_all(args):
    """Stream all RUM events."""
    client = require_auth()
    event_type = RumEventType(args.type) if args.type else None
    
    count = 0
    for event in client.rum_fetch_all(args.query, args.hours, args.max, event_type=event_type):
        emit_json(event)
        count += 1
    
    print(f"Fetched {count} RUM events", file=sys.stderr)


def cmd_rum_top(args):
    """Aggregate RUM events by field."""
    client = require_auth()
    result = client.rum_aggregate(args.query, args.hours, args.field, args.limit)
    emit_json(result, compact=not args.pretty)


# =============================================================================
# Field Exploration Command Handlers
# =============================================================================

def cmd_fields_search(args):
    """Search available fields."""
    client = require_auth()
    result = client.search_fields(args.keyword, DataSource(args.source))
    emit_json(result, compact=not args.pretty)


def cmd_fields_values(args):
    """Get field values (autocomplete)."""
    client = require_auth()
    result = client.field_values(args.field, args.query or "*", DataSource(args.source), args.hours)
    emit_json(result, compact=not args.pretty)


# =============================================================================
# Watchdog & Views Command Handlers
# =============================================================================

def cmd_watchdog(args):
    """Search Watchdog insights."""
    client = require_auth()
    result = client.watchdog_insights(args.query, args.hours, DataSource(args.source))
    emit_json(result, compact=not args.pretty)


def cmd_views_list(args):
    """List saved views."""
    client = require_auth()
    result = client.list_views(args.search or "", DataSource(args.source), args.limit)
    emit_json(result, compact=not args.pretty)


# =============================================================================
# Service Topology Command Handlers
# =============================================================================

def cmd_topology(args):
    """Get service topology/dependency graph."""
    client = require_auth()
    result = client.get_service_topology(
        env=args.env,
        hours=args.hours,
        service_filter=args.service,
    )
    emit_json(result, compact=not args.pretty)


# =============================================================================
# CLI Parser
# =============================================================================

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dd-cli",
        description="Datadog CLI V2 - Query logs using internal web UI APIs",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # --- auth ---
    p_auth = subparsers.add_parser("auth", help="Interactive auth setup")
    p_auth.set_defaults(func=cmd_auth)
    
    # --- status ---
    p_status = subparsers.add_parser("status", help="Check auth status")
    p_status.set_defaults(func=cmd_status)
    
    # --- list ---
    p_list = subparsers.add_parser("list", help="List logs matching query")
    p_list.add_argument("query", help="Search query")
    p_list.add_argument("--hours", type=float, default=1, help="Hours back (default: 1)")
    p_list.add_argument("--limit", type=int, default=100, help="Max logs (default: 100)")
    p_list.add_argument("--profile", default="list", choices=list_profiles(),
                        help="Column profile")
    p_list.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_list.set_defaults(func=cmd_list)
    
    # --- fetch-one ---
    p_fetch_one = subparsers.add_parser("fetch-one", help="Fetch single log details")
    p_fetch_one.add_argument("log_id", help="Log ID")
    p_fetch_one.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_fetch_one.set_defaults(func=cmd_fetch_one)
    
    # --- fetch-all ---
    p_fetch_all = subparsers.add_parser("fetch-all", help="Stream all logs (NDJSON)")
    p_fetch_all.add_argument("query", help="Search query")
    p_fetch_all.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_fetch_all.add_argument("--max", type=int, default=1000, help="Max logs (default: 1000)")
    p_fetch_all.add_argument("--profile", default="list", choices=list_profiles(),
                             help="Column profile")
    p_fetch_all.set_defaults(func=cmd_fetch_all)
    
    # --- deep ---
    p_deep = subparsers.add_parser("deep", help="Fetch logs with full hydration")
    p_deep.add_argument("query", help="Search query")
    p_deep.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_deep.add_argument("--max", type=int, default=50, help="Max logs (default: 50)")
    p_deep.add_argument("--concurrency", type=int, default=4, help="Parallel workers (default: 4)")
    p_deep.add_argument("--profile", default="list", choices=list_profiles(),
                        help="Column profile")
    p_deep.set_defaults(func=cmd_deep)
    
    # --- top ---
    p_top = subparsers.add_parser("top", help="Top values for a field")
    p_top.add_argument("query", help="Search query")
    p_top.add_argument("--field", default="service", help="Field to aggregate (default: service)")
    p_top.add_argument("--hours", type=float, default=1, help="Hours back (default: 1)")
    p_top.add_argument("--limit", type=int, default=10, help="Top N (default: 10)")
    p_top.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_top.set_defaults(func=cmd_top)
    
    # --- facet-info ---
    p_facet = subparsers.add_parser("facet-info", help="Facet metadata/stats")
    p_facet.add_argument("query", help="Search query")
    p_facet.add_argument("--facet", default="service", help="Facet path (default: service)")
    p_facet.add_argument("--hours", type=float, default=1, help="Hours back (default: 1)")
    p_facet.add_argument("--limit", type=int, default=50, help="Max values (default: 50)")
    p_facet.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_facet.set_defaults(func=cmd_facet_info)
    
    # --- trace ---
    p_trace = subparsers.add_parser("trace", help="Find logs for a trace_id")
    p_trace.add_argument("trace_id", help="Trace ID")
    p_trace.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_trace.add_argument("--limit", type=int, default=200, help="Max logs (default: 200)")
    p_trace.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_trace.set_defaults(func=cmd_trace)
    
    # =========================================================================
    # RUM Subcommand Group
    # =========================================================================
    p_rum = subparsers.add_parser(
        "rum", 
        help="Query RUM (Real User Monitoring) data",
        description="""Query Datadog Real User Monitoring (RUM) data.

RUM captures frontend user interactions: sessions, page views, clicks, 
network requests, and JavaScript errors.

Examples:
  dd-cli rum sessions 'C-13947' --hours 48
  dd-cli rum actions '"retrieve rates"' --hours 24
  dd-cli rum errors '@usr.id:alice@example.com' --limit 50

See also: dd-cli list (backend logs), dd-cli fields (explore schema)""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rum_subs = p_rum.add_subparsers(dest="rum_command", required=True)
    
    # rum sessions
    p_rum_sessions = rum_subs.add_parser("sessions", help="Query user sessions")
    p_rum_sessions.add_argument("query", help="Search query (e.g., customer ID, user email)")
    p_rum_sessions.add_argument("--hours", type=float, default=48, help="Hours back (default: 48)")
    p_rum_sessions.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p_rum_sessions.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_rum_sessions.set_defaults(func=cmd_rum_sessions)
    
    # rum actions
    p_rum_actions = rum_subs.add_parser("actions", help="Query user actions (clicks, inputs)")
    p_rum_actions.add_argument("query", help="Search query")
    p_rum_actions.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_rum_actions.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p_rum_actions.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_rum_actions.set_defaults(func=cmd_rum_actions)
    
    # rum views
    p_rum_views = rum_subs.add_parser("views", help="Query page views")
    p_rum_views.add_argument("query", help="Search query")
    p_rum_views.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_rum_views.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p_rum_views.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_rum_views.set_defaults(func=cmd_rum_views)
    
    # rum errors  
    p_rum_errors = rum_subs.add_parser("errors", help="Query frontend JS errors")
    p_rum_errors.add_argument("query", help="Search query")
    p_rum_errors.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_rum_errors.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p_rum_errors.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_rum_errors.set_defaults(func=cmd_rum_errors)
    
    # rum resources
    p_rum_resources = rum_subs.add_parser("resources", help="Query network resources (XHR, fetch)")
    p_rum_resources.add_argument("query", help="Search query")
    p_rum_resources.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_rum_resources.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p_rum_resources.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_rum_resources.set_defaults(func=cmd_rum_resources)
    
    # rum fetch-all
    p_rum_fetch_all = rum_subs.add_parser("fetch-all", help="Stream all RUM events (NDJSON)")
    p_rum_fetch_all.add_argument("query", help="Search query")
    p_rum_fetch_all.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_rum_fetch_all.add_argument("--max", type=int, default=500, help="Max events (default: 500)")
    p_rum_fetch_all.add_argument("--type", choices=["session", "view", "action", "resource", "error"],
                                  help="Filter by event type")
    p_rum_fetch_all.set_defaults(func=cmd_rum_fetch_all)
    
    # rum top
    p_rum_top = rum_subs.add_parser("top", help="Aggregate RUM events by field")
    p_rum_top.add_argument("query", help="Search query")
    p_rum_top.add_argument("--field", default="log_type", help="Field to aggregate (default: log_type)")
    p_rum_top.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_rum_top.add_argument("--limit", type=int, default=10, help="Top N (default: 10)")
    p_rum_top.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_rum_top.set_defaults(func=cmd_rum_top)
    
    # =========================================================================
    # Fields Subcommand Group
    # =========================================================================
    p_fields = subparsers.add_parser(
        "fields",
        help="Explore available fields (autocomplete)",
        description="""Explore field schema and values for logs or RUM.

Useful for discovering available search fields and their values.

Examples:
  dd-cli fields search 'usr' --source rum
  dd-cli fields values '@usr.id' --source rum --hours 24""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    fields_subs = p_fields.add_subparsers(dest="fields_command", required=True)
    
    # fields search
    p_fields_search = fields_subs.add_parser("search", help="Search field names by keyword")
    p_fields_search.add_argument("keyword", help="Partial field name (e.g., 'usr' → @usr.id)")
    p_fields_search.add_argument("--source", choices=["logs", "rum"], default="logs",
                                  help="Data source (default: logs)")
    p_fields_search.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_fields_search.set_defaults(func=cmd_fields_search)
    
    # fields values
    p_fields_values = fields_subs.add_parser("values", help="Get values for a field (autocomplete)")
    p_fields_values.add_argument("field", help="Field path (e.g., '@usr.id', 'service')")
    p_fields_values.add_argument("--query", help="Optional filter query")
    p_fields_values.add_argument("--source", choices=["logs", "rum"], default="logs",
                                  help="Data source (default: logs)")
    p_fields_values.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_fields_values.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_fields_values.set_defaults(func=cmd_fields_values)
    
    # =========================================================================
    # Watchdog Subcommand
    # =========================================================================
    p_watchdog = subparsers.add_parser(
        "watchdog",
        help="Search Watchdog AI insights",
        description="""Search Watchdog insights for anomaly detection.

Watchdog uses AI to detect anomalies in your logs and RUM data.

Examples:
  dd-cli watchdog 'status:error' --hours 24
  dd-cli watchdog 'service:pricing' --source logs""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_watchdog.add_argument("query", help="Search query")
    p_watchdog.add_argument("--hours", type=float, default=24, help="Hours back (default: 24)")
    p_watchdog.add_argument("--source", choices=["logs", "rum"], default="logs",
                            help="Data source (default: logs)")
    p_watchdog.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_watchdog.set_defaults(func=cmd_watchdog)
    
    # =========================================================================
    # Views Subcommand Group
    # =========================================================================
    p_views = subparsers.add_parser(
        "views",
        help="List saved Datadog views",
        description="""List saved views in Datadog.

Saved views are pre-configured search queries shared by your team.

Examples:
  dd-cli views list --source logs
  dd-cli views list --search 'pricing' --source rum""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    views_subs = p_views.add_subparsers(dest="views_command", required=True)
    
    # views list
    p_views_list = views_subs.add_parser("list", help="List saved views")
    p_views_list.add_argument("--search", help="Search term for view names")
    p_views_list.add_argument("--source", choices=["logs", "rum"], default="logs",
                               help="Data source (default: logs)")
    p_views_list.add_argument("--limit", type=int, default=10, help="Max views (default: 10)")
    p_views_list.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_views_list.set_defaults(func=cmd_views_list)
    
    # =========================================================================
    # Topology Subcommand
    # =========================================================================
    p_topology = subparsers.add_parser(
        "topology",
        help="Get service dependency graph",
        description="""Get service topology/dependency graph from APM.

Shows nodes (services) with health status and edges (dependencies).

Examples:
  dd-cli topology --env sandbox --hours 1 --pretty
  dd-cli topology --env sandbox --service pricing --pretty""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_topology.add_argument("--env", default="sandbox", help="Environment (default: sandbox)")
    p_topology.add_argument("--hours", type=float, default=1, help="Hours back (default: 1)")
    p_topology.add_argument("--service", help="Filter to specific service and neighbors")
    p_topology.add_argument("--pretty", action="store_true", help="Pretty print JSON")
    p_topology.set_defaults(func=cmd_topology)
    
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
