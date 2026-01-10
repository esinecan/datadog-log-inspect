"""Datadog Web Logs API Client - Internal API wrapper.

Supports both logs and RUM data sources via the DataSource enum.
"""

import json
import sys
import time
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import Auth
from .profiles import get_profile


class DataSource(Enum):
    """Datadog data source types."""
    LOGS = "logs"
    RUM = "rum"


class RumEventType(Enum):
    """RUM event types for filtering."""
    SESSION = "session"
    VIEW = "view"
    ACTION = "action"
    RESOURCE = "resource"
    ERROR = "error"
    LONG_TASK = "long_task"


class DatadogWebLogs:
    """Client for Datadog's internal web UI logs API."""
    
    def __init__(self, auth: Auth, user_agent: str = "dd-cli-v2"):
        self.auth = auth
        self.session = self._create_session(user_agent)
    
    def _create_session(self, user_agent: str) -> requests.Session:
        """Create a session with retry logic."""
        session = requests.Session()
        
        # Retry strategy for transient errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Set headers
        session.headers.update({
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": user_agent,
            "x-csrf-token": self.auth.csrf_token,
        })
        session.cookies.set("dogweb", self.auth.dogweb_cookie)
        
        return session
    
    def _post(self, path: str, payload: Dict[str, Any]) -> requests.Response:
        """POST request to Datadog API."""
        url = f"{self.auth.base_url}{path}"
        response = self.session.post(url, data=json.dumps(payload))
        response.raise_for_status()
        return response
    
    def _get(self, path: str) -> requests.Response:
        """GET request to Datadog API."""
        url = f"{self.auth.base_url}{path}"
        response = self.session.get(url)
        response.raise_for_status()
        return response
    
    def _extract_cursor(self, resp_json: Dict[str, Any], 
                        response: requests.Response) -> Optional[str]:
        """Extract pagination cursor from response (multi-path)."""
        # Try body paths first
        result = resp_json.get("result", {}) or {}
        
        # Path 1: .result.nextLogId
        cursor = result.get("nextLogId")
        if cursor:
            return cursor
        
        # Path 2: .meta.page.after
        meta = resp_json.get("meta", {}) or {}
        page = meta.get("page", {}) or {}
        after = page.get("after")
        if after:
            return after
        
        # Path 3: Response headers
        for header in ["x-datadog-next-log-id", "X-Datadog-Next-Log-Id"]:
            if header in response.headers:
                return response.headers[header]
        
        return None
    
    def _time_range_ms(self, hours: float) -> tuple[int, int]:
        """Calculate time range in milliseconds."""
        now_ms = int(time.time() * 1000)
        from_ms = int(now_ms - hours * 3600 * 1000)
        return from_ms, now_ms
    
    # =========================================================================
    # Core API Methods
    # =========================================================================
    
    def list_logs(self, query: str, hours: float = 1, limit: int = 100,
                  profile: str = "list", cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        List logs matching query.
        
        Endpoint: /api/v1/logs-analytics/list?type=logs
        """
        from_ms, to_ms = self._time_range_ms(hours)
        columns = get_profile(profile)
        
        body = {
            "list": {
                "columns": columns,
                "sort": {"time": {"order": "desc"}},
                "limit": limit,
                "time": {"from": from_ms, "to": to_ms},
                "search": {"query": query},
                "indexes": ["*"],
                "includeEvents": True,
                "computeCount": False,
                "executionInfo": {},
            }
        }
        
        if cursor:
            body["list"]["startAt"] = cursor
        
        return self._post("/api/v1/logs-analytics/list?type=logs", body).json()
    
    def fetch_one(self, log_id: str) -> Dict[str, Any]:
        """
        Fetch full details of a single log entry.
        
        Endpoint: /api/v1/logs-analytics/fetch_one?type=logs
        """
        body = {
            "fetch_one": {
                "id": log_id,
                "indexes": ["*"],
                "executionInfo": {},
            }
        }
        return self._post("/api/v1/logs-analytics/fetch_one?type=logs", body).json()
    
    def aggregate(self, query: str, hours: float = 1, field: str = "service",
                  limit: int = 10) -> Dict[str, Any]:
        """
        Aggregate logs by field (top values).
        
        Endpoint: /api/v1/logs-analytics/aggregate?type=logs
        """
        from_ms, to_ms = self._time_range_ms(hours)
        
        body = {
            "aggregate": {
                "compute": [
                    {
                        "timeseries": {
                            "metric": "count",
                            "output": "count:count:timeseries",
                            "aggregation": "count",
                            "interval": 60000,  # 1 minute intervals
                        }
                    }
                ],
                "time": {"from": from_ms, "to": to_ms},
                "indexes": ["*"],
                "executionInfo": {},
                "search": {"query": query},
                "groupBy": [{
                    "field": {
                        "id": field,
                        "output": field,
                        "sort": {
                            "metric": {"id": "count:count", "order": "desc"}
                        },
                        "limit": limit,
                    }
                }],
                "calculatedFields": [],
            }
        }
        return self._post("/api/v1/logs-analytics/aggregate?type=logs", body).json()
    
    def facet_info(self, query: str, hours: float = 1, facet: str = "service",
                   limit: int = 50) -> Dict[str, Any]:
        """
        Get facet metadata/stats for a field.
        
        Endpoint: /api/v1/logs-analytics/facet_info?type=logs
        """
        from_ms, to_ms = self._time_range_ms(hours)
        
        body = {
            "facet_info": {
                "metric": "count",
                "limit": limit,
                "indexes": ["*"],
                "time": {"from": from_ms, "to": to_ms},
                "aggregation": "count",
                "search": {"query": query},
                "termSearch": {"query": ""},
                "path": facet,
                "executionInfo": {},
                "calculatedFields": [],
                "extractions": [],
            }
        }
        return self._post("/api/v1/logs-analytics/facet_info?type=logs", body).json()
    
    # =========================================================================
    # Streaming / Pagination Methods
    # =========================================================================
    
    def fetch_all(self, query: str, hours: float = 24, 
                  page_size: int = 100, max_logs: int = 1000,
                  profile: str = "list") -> Iterator[Dict[str, Any]]:
        """
        Stream all logs matching query with pagination (NDJSON).
        
        Yields individual log events.
        """
        cursor = None
        seen = 0
        
        while seen < max_logs:
            try:
                response = self._post(
                    "/api/v1/logs-analytics/list?type=logs",
                    self._build_list_body(query, hours, page_size, profile, cursor)
                )
                data = response.json()
            except requests.HTTPError as e:
                print(f"HTTP Error: {e}", file=sys.stderr)
                break
            
            result = data.get("result", {}) or {}
            events = result.get("events", []) or []
            
            if not events:
                break
            
            for event in events:
                yield event
                seen += 1
                if seen >= max_logs:
                    break
            
            cursor = self._extract_cursor(data, response)
            if not cursor:
                break
            
            # Light pacing to avoid rate limits
            time.sleep(0.05)
    
    def _build_list_body(self, query: str, hours: float, limit: int,
                         profile: str, cursor: Optional[str]) -> Dict[str, Any]:
        """Build list request body."""
        from_ms, to_ms = self._time_range_ms(hours)
        columns = get_profile(profile)
        
        body = {
            "list": {
                "columns": columns,
                "sort": {"time": {"order": "desc"}},
                "limit": limit,
                "time": {"from": from_ms, "to": to_ms},
                "search": {"query": query},
                "indexes": ["*"],
                "includeEvents": True,
                "computeCount": False,
                "executionInfo": {},
            }
        }
        
        if cursor:
            body["list"]["startAt"] = cursor
        
        return body
    
    def deep_fetch(self, query: str, hours: float = 24,
                   max_logs: int = 50, concurrency: int = 4,
                   profile: str = "list") -> Iterator[Dict[str, Any]]:
        """
        Fetch logs with full hydration (list + fetch_one per log).
        
        Yields enriched log objects with both list and full event data.
        """
        # Step 1: Get list of logs
        events = list(self.fetch_all(query, hours, 100, max_logs, profile))
        
        if not events:
            return
        
        print(f"Hydrating {len(events)} logs with concurrency={concurrency}...", 
              file=sys.stderr)
        
        # Step 2: Extract IDs and hydrate in parallel
        def hydrate(event: Dict[str, Any]) -> Dict[str, Any]:
            log_id = event.get("event", {}).get("id") or event.get("id")
            if not log_id:
                return {"list_event": event, "full_event": None, "error": "no_id"}
            
            try:
                full = self.fetch_one(log_id)
                return {"list_event": event, "full_event": full}
            except Exception as e:
                return {"list_event": event, "full_event": None, "error": str(e)}
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(hydrate, e): e for e in events}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    yield result
                except Exception as e:
                    print(f"Hydration error: {e}", file=sys.stderr)
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    def trace_logs(self, trace_id: str, hours: float = 24,
                   limit: int = 200) -> Dict[str, Any]:
        """Find all logs for a specific trace_id."""
        return self.list_logs(f"trace_id:{trace_id}", hours, limit, profile="trace")
    
    def test_connection(self) -> bool:
        """Test if the authentication is valid."""
        try:
            result = self.list_logs("*", hours=0.01, limit=1)
            return "result" in result
        except Exception:
            return False
    
    # =========================================================================
    # RUM API Methods
    # =========================================================================
    
    def rum_list(self, query: str, hours: float = 24, limit: int = 100,
                 event_type: Optional[RumEventType] = None,
                 cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        List RUM events matching query.
        
        Endpoint: /api/v1/logs-analytics/list?type=rum
        
        Args:
            query: Search query (can include customer IDs, user emails, etc.)
            hours: Hours back to search
            limit: Max results per page
            event_type: Optional filter by RUM type (session, action, view, etc.)
            cursor: Pagination cursor from previous response
        """
        from_ms, to_ms = self._time_range_ms(hours)
        
        # Build query with optional type filter
        full_query = query
        if event_type:
            full_query = f"@type:{event_type.value} {query}".strip()
        
        # RUM-specific columns
        columns = [
            {"field": {"path": "timestamp"}},
            {"field": {"path": "@type"}},
            {"field": {"path": "@session.id"}},
            {"field": {"path": "@usr.id"}},
            {"field": {"path": "@view.name"}},
            {"field": {"path": "@action.name"}},
            {"field": {"path": "@error.message"}},
        ]
        
        body = {
            "list": {
                "columns": columns,
                "sort": {"time": {"order": "desc"}},
                "limit": limit,
                "time": {"from": from_ms, "to": to_ms},
                "search": {"query": full_query},
                "indexes": ["*"],
                "includeEvents": True,
                "computeCount": False,
                "executionInfo": {},
            }
        }
        
        if cursor:
            body["list"]["startAt"] = cursor
        
        return self._post("/api/v1/logs-analytics/list?type=rum", body).json()
    
    def rum_sessions(self, query: str, hours: float = 24, 
                     limit: int = 100) -> Dict[str, Any]:
        """Query RUM sessions for a user/customer."""
        return self.rum_list(query, hours, limit, RumEventType.SESSION)
    
    def rum_actions(self, query: str, hours: float = 24,
                    limit: int = 100) -> Dict[str, Any]:
        """Query RUM user actions (clicks, inputs, navigations)."""
        return self.rum_list(query, hours, limit, RumEventType.ACTION)
    
    def rum_views(self, query: str, hours: float = 24,
                  limit: int = 100) -> Dict[str, Any]:
        """Query RUM page views."""
        return self.rum_list(query, hours, limit, RumEventType.VIEW)
    
    def rum_errors(self, query: str, hours: float = 24,
                   limit: int = 100) -> Dict[str, Any]:
        """Query RUM frontend errors."""
        return self.rum_list(query, hours, limit, RumEventType.ERROR)
    
    def rum_resources(self, query: str, hours: float = 24,
                      limit: int = 100) -> Dict[str, Any]:
        """Query RUM network resources (XHR, fetch, assets)."""
        return self.rum_list(query, hours, limit, RumEventType.RESOURCE)
    
    def rum_aggregate(self, query: str, hours: float = 24, 
                      field: str = "log_type", limit: int = 10) -> Dict[str, Any]:
        """
        Aggregate RUM events by field.
        
        Endpoint: /api/v1/logs-analytics/aggregate?type=rum
        """
        from_ms, to_ms = self._time_range_ms(hours)
        
        body = {
            "aggregate": {
                "compute": [
                    {
                        "timeseries": {
                            "metric": "count",
                            "output": "count:count:timeseries",
                            "aggregation": "count",
                            "interval": 60000,
                        }
                    }
                ],
                "time": {"from": from_ms, "to": to_ms},
                "indexes": ["*"],
                "executionInfo": {},
                "search": {"query": query},
                "groupBy": [{
                    "field": {
                        "id": field,
                        "output": field,
                        "sort": {
                            "metric": {"id": "count:count", "order": "desc"}
                        },
                        "limit": limit,
                    }
                }],
                "calculatedFields": [],
            }
        }
        return self._post("/api/v1/logs-analytics/aggregate?type=rum", body).json()
    
    def rum_fetch_all(self, query: str, hours: float = 24, 
                      max_logs: int = 500, page_size: int = 100,
                      event_type: Optional[RumEventType] = None) -> Iterator[Dict[str, Any]]:
        """Stream all RUM events matching query with pagination."""
        cursor = None
        seen = 0
        
        while seen < max_logs:
            try:
                response = self._post(
                    "/api/v1/logs-analytics/list?type=rum",
                    self._build_rum_list_body(query, hours, page_size, event_type, cursor)
                )
                data = response.json()
            except requests.HTTPError as e:
                print(f"HTTP Error: {e}", file=sys.stderr)
                break
            
            result = data.get("result", {}) or {}
            events = result.get("events", []) or []
            
            if not events:
                break
            
            for event in events:
                yield event
                seen += 1
                if seen >= max_logs:
                    break
            
            cursor = self._extract_cursor(data, response)
            if not cursor:
                break
            
            time.sleep(0.05)
    
    def _build_rum_list_body(self, query: str, hours: float, limit: int,
                              event_type: Optional[RumEventType],
                              cursor: Optional[str]) -> Dict[str, Any]:
        """Build RUM list request body."""
        from_ms, to_ms = self._time_range_ms(hours)
        
        full_query = query
        if event_type:
            full_query = f"@type:{event_type.value} {query}".strip()
        
        columns = [
            {"field": {"path": "timestamp"}},
            {"field": {"path": "@type"}},
            {"field": {"path": "@session.id"}},
            {"field": {"path": "@usr.id"}},
            {"field": {"path": "@view.name"}},
            {"field": {"path": "@action.name"}},
            {"field": {"path": "@error.message"}},
        ]
        
        body = {
            "list": {
                "columns": columns,
                "sort": {"time": {"order": "desc"}},
                "limit": limit,
                "time": {"from": from_ms, "to": to_ms},
                "search": {"query": full_query},
                "indexes": ["*"],
                "includeEvents": True,
                "computeCount": False,
                "executionInfo": {},
            }
        }
        
        if cursor:
            body["list"]["startAt"] = cursor
        
        return body
    
    # =========================================================================
    # Field Exploration API Methods
    # =========================================================================
    
    def search_fields(self, keyword: str, source: DataSource = DataSource.LOGS) -> Dict[str, Any]:
        """
        Search available fields by keyword.
        
        Endpoint: /api/ui/event-platform/query/field
        
        Args:
            keyword: Partial field name to search (e.g., "usr" → @usr.id, @usr.company)
            source: Data source to search in
        """
        body = {
            "type": source.value,
            "term": keyword,
        }
        return self._post("/api/ui/event-platform/query/field", body).json()
    
    def field_values(self, field: str, query: str = "*", 
                     source: DataSource = DataSource.LOGS,
                     hours: float = 24) -> Dict[str, Any]:
        """
        Get possible values for a field (autocomplete).
        
        Endpoint: /api/ui/event-platform/query/field-value
        
        Args:
            field: Field path (e.g., "@usr.id", "service")
            query: Optional filter query
            source: Data source
            hours: Time range
        """
        from_ms, to_ms = self._time_range_ms(hours)
        
        body = {
            "type": source.value,
            "field": field,
            "search": {"query": query},
            "time": {"from": from_ms, "to": to_ms},
        }
        return self._post("/api/ui/event-platform/query/field-value", body).json()
    
    # =========================================================================
    # Service Map / Topology API Methods
    # =========================================================================
    
    def get_service_topology(
        self, 
        env: str = "sandbox",
        hours: float = 1,
        service_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get service topology/dependency graph.
        
        Returns nodes (services) and edges (dependencies) with health status.
        
        Endpoint: /api/unstable/apm/entities/graph
        
        Args:
            env: Environment filter (e.g., "sandbox", "production")
            hours: Hours back to query (default: 1)
            service_filter: Optional service name to filter graph around
            
        Returns:
            {
                "nodes": [{"service": "pricing", "health": "ok", "stats": {...}}, ...],
                "edges": [{"from": "api", "to": "pricing", "operation": "..."}, ...]
            }
        """
        import urllib.parse
        
        from_ms, to_ms = self._time_range_ms(hours)
        
        # Convert to Unix seconds (API expects seconds not milliseconds)
        from_sec = int(from_ms / 1000)
        to_sec = int(to_ms / 1000)
        
        # Step 1: Get nodes (services) from /entities
        entities_params = {
            "filter[env]": env,
            "filter[from]": str(from_sec),
            "filter[to]": str(to_sec),
            "filter[columns]": "SERVICE_NAME,REQUESTS,REQUESTS_PER_SECOND,ERRORS,ERRORS_PERCENTAGE,LATENCY_AVG,LATENCY_P95",
            "filter[entity.type.catalog.kind]": "service",
            "order_by_col": "REQUESTS",
            "order_by_desc": "true",
            "source": "web-ui",
            "page[size]": "1000",  # Get all services
            "page[number]": "0",
            "include": "entity.service_health",
        }
        
        entities_url = f"/api/unstable/apm/entities?{urllib.parse.urlencode(entities_params)}"
        entities_resp = self._get(entities_url)
        entities_data = entities_resp.json()
        
        # Step 2: Get edges from /entities/graph
        graph_params = {
            "filter[env]": env,
            "filter[from]": str(from_sec),
            "filter[to]": str(to_sec),
            "filter[columns]": "OPERATION_NAME,REQUESTS_PER_SECOND,LATENCY_AVG,ERRORS_PERCENTAGE",
            "source": "web-ui",
            "datastore": "metrics",
            "page[size]": "0",
            "return_legacy_fields": "false",
            "include": "entity.service_health",
            "filter[metadata]": "color",
            "graph.hide_service_overrides": "false",
        }
        
        graph_url = f"/api/unstable/apm/entities/graph?{urllib.parse.urlencode(graph_params)}"
        graph_resp = self._get(graph_url)
        graph_data = graph_resp.json()
        
        # Parse nodes from entities response
        nodes = []
        node_id_to_service = {}
        
        for item in entities_data.get("data", []):
            if item.get("type") == "apm-entity":
                attrs = item.get("attributes", {})
                id_tags = attrs.get("id_tags", {})
                service_name = id_tags.get("service", "unknown")
                node_id_to_service[item["id"]] = service_name
                
                # Extract health and stats
                health_info = attrs.get("service_health", {})
                stats_info = attrs.get("stats", {})
                
                nodes.append({
                    "service": service_name,
                    "health": health_info.get("status", "unknown"),
                    "stats": {
                        "requests_per_second": stats_info.get("requests_per_second"),
                        "latency_avg": stats_info.get("latency_avg"),
                        "latency_p95": stats_info.get("latency_p95"),
                        "errors_percentage": stats_info.get("errors_percentage"),
                    },
                })
        
        # Parse edges from graph response
        edges = []
        for item in graph_data.get("data", []):
            if item.get("type") == "apm-entity-edge":
                attrs = item.get("attributes", {})
                rels = item.get("relationships", {})
                
                source_data = rels.get("source", {}).get("data", {})
                target_data = rels.get("target", {}).get("data", {})
                
                source_id = source_data.get("id")
                target_id = target_data.get("id")
                
                if source_id and target_id:
                    edges.append({
                        "from": node_id_to_service.get(source_id, source_id),
                        "to": node_id_to_service.get(target_id, target_id),
                        "operation": attrs.get("operation", ""),
                        "span_kind": attrs.get("span.kind", ""),
                    })
        
        # Optional: filter to specific service and its neighbors
        if service_filter:
            # Keep only nodes connected to service_filter
            connected_services = {service_filter}
            for edge in edges:
                if edge["from"] == service_filter:
                    connected_services.add(edge["to"])
                elif edge["to"] == service_filter:
                    connected_services.add(edge["from"])
            
            nodes = [n for n in nodes if n["service"] in connected_services]
            edges = [e for e in edges if e["from"] in connected_services or e["to"] in connected_services]
        
        return {"nodes": nodes, "edges": edges}
    
    # =========================================================================
    # Watchdog Insights API Methods
    # =========================================================================
    
    def watchdog_insights(self, query: str, hours: float = 24,
                          source: DataSource = DataSource.LOGS) -> Dict[str, Any]:
        """
        Search Watchdog insights for anomalies.
        
        Endpoint: /api/v2/watchdog/insights/search
        
        Args:
            query: Search query
            hours: Time range
            source: Data source (logs or rum)
        """
        from_ms, to_ms = self._time_range_ms(hours)
        
        body = {
            "filter": {
                "query": query,
                "from": from_ms,
                "to": to_ms,
            },
            "source": source.value,
        }
        return self._post("/api/v2/watchdog/insights/search", body).json()
    
    # =========================================================================
    # Saved Views API Methods
    # =========================================================================
    
    def list_views(self, search: str = "", source: DataSource = DataSource.LOGS,
                   limit: int = 10) -> Dict[str, Any]:
        """
        List saved views.
        
        Endpoint: /api/v1/logs/views
        
        Args:
            search: Optional search term for view names
            source: Data source type
            limit: Max views to return
        """
        import urllib.parse
        encoded_search = urllib.parse.quote(search)
        url = f"/api/v1/logs/views?type={source.value}&q={encoded_search}&fullIntegration=false&limit={limit}&filter_by_me=false"
        
        response = self.session.get(f"{self.auth.base_url}{url}")
        response.raise_for_status()
        return response.json()

