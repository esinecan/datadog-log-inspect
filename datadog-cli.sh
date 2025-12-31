#!/bin/bash
# Datadog Log CLI - Query logs using saved auth tokens
# Usage: ./datadog-cli.sh <command> [args]

set -e

# Config
AUTH_FILE="${HOME}/.datadog-auth"
DD_BASE_URL="https://app.datadoghq.eu"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if auth file exists
check_auth() {
    if [[ ! -f "$AUTH_FILE" ]]; then
        echo -e "${RED}No auth file found at $AUTH_FILE${NC}"
        echo "Run: $0 auth"
        exit 1
    fi
    
    # Source the auth file
    source "$AUTH_FILE"
    
    if [[ -z "$DOGWEB_COOKIE" ]] || [[ -z "$CSRF_TOKEN" ]]; then
        echo -e "${RED}Auth file missing DOGWEB_COOKIE or CSRF_TOKEN${NC}"
        echo "Run: $0 auth"
        exit 1
    fi
}

# Setup auth
cmd_auth() {
    echo -e "${YELLOW}Datadog Auth Setup${NC}"
    echo "========================================"
    echo ""
    echo "1. Open https://app.datadoghq.eu/logs in Chrome"
    echo "2. Open DevTools (F12) → Network tab"
    echo "3. Perform any search"
    echo "4. Find a request to 'logs-analytics'"
    echo "5. Right-click → Copy as cURL"
    echo ""
    echo "From that curl command, extract:"
    echo ""
    
    read -p "dogweb cookie value: " dogweb
    read -p "x-csrf-token header value: " csrf
    
    cat > "$AUTH_FILE" << EOF
# Datadog auth tokens - regenerate when expired
# Created: $(date -Iseconds)
DOGWEB_COOKIE="$dogweb"
CSRF_TOKEN="$csrf"
EOF
    
    chmod 600 "$AUTH_FILE"
    echo -e "${GREEN}Auth saved to $AUTH_FILE${NC}"
}

# Query logs
cmd_query() {
    check_auth
    
    local query="$1"
    local hours="${2:-1}"  # Default: last 1 hour
    local limit="${3:-100}"  # Default: 100 logs
    
    if [[ -z "$query" ]]; then
        echo "Usage: $0 query '<search_query>' [hours_back] [limit]"
        echo "Example: $0 query 'service:rates-management-core status:error' 24 50"
        exit 1
    fi
    
    # Calculate time range
    local now_ms=$(($(date +%s) * 1000))
    local from_ms=$((now_ms - hours * 3600 * 1000))
    
    echo -e "${YELLOW}Querying: ${query}${NC}" >&2
    echo -e "Time range: last ${hours}h, limit: ${limit}" >&2
    
    # Build request body
    local body=$(cat << EOF
{
  "list": {
    "columns": [
      {"field": {"path": "timestamp"}},
      {"field": {"path": "host"}},
      {"field": {"path": "service"}},
      {"field": {"path": "trace_id"}},
      {"field": {"path": "content"}}
    ],
    "sort": {"time": {"order": "desc"}},
    "limit": ${limit},
    "time": {"from": ${from_ms}, "to": ${now_ms}},
    "search": {"query": "${query}"},
    "indexes": ["*"]
  },
  "_authentication_token": "${CSRF_TOKEN}"
}
EOF
)
    
    curl -s "${DD_BASE_URL}/api/v1/logs-analytics/list?type=logs" \
        -H 'accept: application/json' \
        -H 'content-type: application/json' \
        -b "dogweb=${DOGWEB_COOKIE}" \
        -H "x-csrf-token: ${CSRF_TOKEN}" \
        --data-raw "$body"
}

# Query and format as simple text (improved message extraction)
cmd_search() {
    check_auth
    
    local query="$1"
    local hours="${2:-1}"
    local limit="${3:-50}"
    
    if [[ -z "$query" ]]; then
        echo "Usage: $0 search '<search_query>' [hours_back] [limit]"
        exit 1
    fi
    
    cmd_query "$query" "$hours" "$limit" | jq -r '
        .result.events[]? | 
        "\(.event.timestamp // .columns[0]) | \(.event.service // .columns[2]) | trace:\(.event.trace_id_low // .columns[3] // "N/A") | \(.event.message // .columns[4] // "no msg")"
    ' 2>/dev/null || echo "No results or error parsing response"
}

# Get trace correlation
cmd_trace() {
    check_auth
    
    local trace_id="$1"
    local hours="${2:-24}"
    
    if [[ -z "$trace_id" ]]; then
        echo "Usage: $0 trace <trace_id> [hours_back]"
        exit 1
    fi
    
    echo -e "${YELLOW}Finding all logs for trace: ${trace_id}${NC}" >&2
    
    cmd_query "trace_id:${trace_id}" "$hours" 200 | jq -r '
        .result.events[]? | 
        "\(.event.timestamp // .columns[0]) | \(.event.service // .columns[2]) | \(.event.message // .columns[4] // "no msg")[0:100]"
    ' 2>/dev/null
}

# Get full log details with attributes (for deep inspection)
cmd_details() {
    check_auth
    
    local query="$1"
    local hours="${2:-24}"
    local limit="${3:-5}"
    
    if [[ -z "$query" ]]; then
        echo "Usage: $0 details '<search_query>' [hours_back] [limit]"
        echo "Returns full log details including nested attributes"
        exit 1
    fi
    
    echo -e "${YELLOW}Fetching full details for: ${query}${NC}" >&2
    echo -e "Time range: last ${hours}h, limit: ${limit}${NC}" >&2
    echo "" >&2
    
    cmd_query "$query" "$hours" "$limit" | jq -r '
        .result.events[]? | 
        "═══════════════════════════════════════════════════════════════════════════════",
        "📅 Timestamp: \(.event.timestamp // .columns[0])",
        "🏷️  Service:   \(.event.service // .columns[2])",
        "🔗 Trace ID:  \(.event.trace_id_low // .columns[3] // "N/A")",
        "📊 Status:    \(.event.status // "unknown")",
        "🆔 Event ID:  \(.event.id // .event_id // "N/A")",
        "───────────────────────────────────────────────────────────────────────────────",
        "📝 Message:",
        "\(.event.message // "no message")",
        "───────────────────────────────────────────────────────────────────────────────",
        "📦 Metadata/Attributes:",
        (
          if .event.custom.metadata.params then 
            "  [params]: " + (.event.custom.metadata.params | tostring | .[0:2000]) + "..."
          elif .event.custom.metadata then 
            (.event.custom.metadata | tostring | .[0:2000])
          elif .event.custom.attributes then 
            (.event.custom.attributes | tostring | .[0:2000])
          else 
            "N/A" 
          end
        ),
        ""
    ' 2>/dev/null || echo "No results or error parsing response"
}

# Get raw JSON details for a single log (for programmatic access)
cmd_raw() {
    check_auth
    
    local query="$1"
    local hours="${2:-24}"
    local limit="${3:-1}"
    
    if [[ -z "$query" ]]; then
        echo "Usage: $0 raw '<search_query>' [hours_back] [limit]"
        echo "Returns raw JSON for log events (pipe to jq for filtering)"
        exit 1
    fi
    
    cmd_query "$query" "$hours" "$limit" | jq '.result.events[]?.event' 2>/dev/null
}

# Check auth status
cmd_status() {
    if [[ -f "$AUTH_FILE" ]]; then
        source "$AUTH_FILE"
        echo -e "${GREEN}Auth file exists${NC}: $AUTH_FILE"
        echo "Cookie length: ${#DOGWEB_COOKIE} chars"
        echo "CSRF token: ${CSRF_TOKEN:0:20}..."
        
        # Test with a simple query
        echo ""
        echo "Testing connection..."
        local result=$(cmd_query "service:*" 1 1 2>/dev/null)
        if echo "$result" | jq -e '.result.events' >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Connection successful${NC}"
        else
            echo -e "${RED}✗ Connection failed - tokens may be expired${NC}"
            echo "$result" | head -c 200
        fi
    else
        echo -e "${RED}No auth file${NC}"
        echo "Run: $0 auth"
    fi
}

# Help
cmd_help() {
    echo "Datadog Log CLI"
    echo ""
    echo "Commands:"
    echo "  auth               Setup authentication (interactive)"
    echo "  status             Check auth status and test connection"
    echo "  query <q> [h] [n]  Raw JSON query (hours back, limit)"
    echo "  search <q> [h] [n] Search and format as text"
    echo "  details <q> [h] [n] Full log details with metadata"
    echo "  raw <q> [h] [n]    Raw JSON event data (for jq piping)"
    echo "  trace <id> [h]     Get all logs for a trace_id"
    echo ""
    echo "Examples:"
    echo "  $0 auth"
    echo "  $0 search 'S1124801' 24 100"
    echo "  $0 search 'service:rates-management-core status:error' 1 50"
    echo "  $0 details 'Pricing engine could not find any quotes' 24 3"
    echo "  $0 raw 'C-62077' 48 1 | jq '.custom.metadata'"
    echo "  $0 trace 6035712778155264233"
    echo "  $0 query 'env:production error' 12 200 | jq '.result.count'"
}

# Main
case "${1:-help}" in
    auth)    cmd_auth ;;
    status)  cmd_status ;;
    query)   cmd_query "$2" "$3" "$4" ;;
    search)  cmd_search "$2" "$3" "$4" ;;
    details) cmd_details "$2" "$3" "$4" ;;
    raw)     cmd_raw "$2" "$3" "$4" ;;
    trace)   cmd_trace "$2" "$3" ;;
    help|*)  cmd_help ;;
esac
