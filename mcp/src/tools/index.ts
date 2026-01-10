/**
 * Tool definitions and handler dispatch for datadog-mcp
 */

import { Tool } from "@modelcontextprotocol/sdk/types.js";
import { execDdCliJson } from "../core/executor.js";

export const TOOLS: Tool[] = [
    {
        name: "dd_auth_status",
        description: "Check Datadog authentication status",
        inputSchema: {
            type: "object",
            properties: {},
            required: [],
        },
    },
    {
        name: "dd_search_logs",
        description: "Search Datadog backend logs. Use for: finding errors (service:pricing status:error), shipment logs (S1234567), trace correlation (trace_id:abc123)",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Datadog search query (same syntax as web UI)" },
                hours: { type: "number", description: "Hours back to search (default: 24)", default: 24 },
                limit: { type: "number", description: "Max results (default: 50)", default: 50 },
            },
            required: ["query"],
        },
    },
    {
        name: "dd_trace_logs",
        description: "Get all logs for a specific trace_id. Use to follow a request across multiple services.",
        inputSchema: {
            type: "object",
            properties: {
                trace_id: { type: "string", description: "The trace ID to search for" },
                hours: { type: "number", description: "Hours back to search (default: 24)", default: 24 },
                limit: { type: "number", description: "Max logs (default: 200)", default: 200 },
            },
            required: ["trace_id"],
        },
    },
    {
        name: "dd_fetch_log",
        description: "Fetch full details of a single log entry. Use log_id + source_fragment_id from search results.",
        inputSchema: {
            type: "object",
            properties: {
                log_id: { type: "string", description: "The log ID from a previous search" },
                source_fragment_id: { type: "string", description: "The source_fragment_id from a previous search (required for fetch to work)" },
            },
            required: ["log_id", "source_fragment_id"],
        },
    },
    {
        name: "dd_top_values",
        description: "Aggregate top values for a field in matching logs. Use for: finding which services have errors, distribution by status.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Datadog search query" },
                field: { type: "string", description: "Field to aggregate (default: service)", default: "service" },
                hours: { type: "number", description: "Hours back (default: 24)", default: 24 },
                limit: { type: "number", description: "Top N values (default: 10)", default: 10 },
            },
            required: ["query"],
        },
    },
    {
        name: "dd_get_topology",
        description: "Get service dependency graph/topology. Use for: finding downstream dependencies, identifying services in ALERT state, root cause analysis across microservices.",
        inputSchema: {
            type: "object",
            properties: {
                env: { type: "string", description: "Environment filter (e.g., 'sandbox', 'production') (default: sandbox)", default: "sandbox" },
                hours: { type: "number", description: "Hours back (default: 1)", default: 1 },
                service: { type: "string", description: "Optional: Filter to specific service and its neighbors" },
            },
            required: [],
        },
    },
    // =============================================================================
    // RUM (Real User Monitoring) Tools
    // =============================================================================
    {
        name: "dd_rum_sessions",
        description: "Query RUM user sessions. Use for: finding sessions for a customer ID or user email, seeing the initiation point of a workflow.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Search query (customer ID like C-13947, user email, shipment ID)" },
                hours: { type: "number", description: "Hours back to search (default: 48)", default: 48 },
                limit: { type: "number", description: "Max results (default: 50)", default: 50 },
            },
            required: ["query"],
        },
    },
    {
        name: "dd_rum_actions",
        description: "Query RUM user actions (clicks, inputs, navigations). Use for: finding what button a user clicked, form submissions.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Search query (action name, customer ID)" },
                hours: { type: "number", description: "Hours back (default: 24)", default: 24 },
                limit: { type: "number", description: "Max results (default: 50)", default: 50 },
            },
            required: ["query"],
        },
    },
    {
        name: "dd_rum_errors",
        description: "Query RUM frontend JavaScript errors. Use for: finding JS crashes, console errors for a user or page.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Search query (user email, page path, error message)" },
                hours: { type: "number", description: "Hours back (default: 24)", default: 24 },
                limit: { type: "number", description: "Max results (default: 50)", default: 50 },
            },
            required: ["query"],
        },
    },
    {
        name: "dd_rum_resources",
        description: "Query RUM network resources (XHR, fetch, assets). Use for: finding failed API calls, slow requests in the browser.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Search query (URL pattern, status codes)" },
                hours: { type: "number", description: "Hours back (default: 24)", default: 24 },
                limit: { type: "number", description: "Max results (default: 50)", default: 50 },
            },
            required: ["query"],
        },
    },
    // =============================================================================
    // Field Discovery Tools
    // =============================================================================
    {
        name: "dd_fields_search",
        description: "[BROKEN - API returns 400] Search available field names by keyword. WORKAROUND: Use dd_top_values instead to discover field values.",
        inputSchema: {
            type: "object",
            properties: {
                keyword: { type: "string", description: "Partial field name to search (e.g., 'usr', 'shipment', 'customer')" },
                source: { type: "string", enum: ["logs", "rum"], description: "Data source (default: logs)", default: "logs" },
            },
            required: ["keyword"],
        },
    },
    {
        name: "dd_fields_values",
        description: "[BROKEN - API returns 400] Get autocomplete values for a field. WORKAROUND: Use dd_top_values with the field parameter instead.",
        inputSchema: {
            type: "object",
            properties: {
                field: { type: "string", description: "Field path (e.g., '@usr.id', 'service', '@shipment.id')" },
                query: { type: "string", description: "Optional filter query to narrow values" },
                source: { type: "string", enum: ["logs", "rum"], description: "Data source (default: logs)", default: "logs" },
                hours: { type: "number", description: "Hours back (default: 24)", default: 24 },
            },
            required: ["field"],
        },
    },
];

interface LogEvent {
    timestamp?: string;
    service?: string;
    status?: string;
    message?: string;
    trace_id?: string;
    id?: string;
    source_fragment_id?: string;
}

interface LogResult {
    result?: {
        events?: Array<{ event?: LogEvent }>;
    };
}

function simplifyLogEvent(event: Record<string, unknown>): LogEvent {
    return {
        timestamp: event.timestamp as string,
        service: event.service as string,
        status: event.status as string,
        message: ((event.message as string) || "").substring(0, 2000),
        trace_id: event.trace_id as string,
        id: event.id as string,
        source_fragment_id: event.source_fragment_id as string,
    };
}

function simplifyLogs(result: LogResult): { count: number; events: LogEvent[] } {
    const events = result.result?.events || [];
    const simplified = events.map((e) => simplifyLogEvent(e.event as any || {}));
    return { count: simplified.length, events: simplified };
}

export async function handleToolCall(
    name: string,
    args: Record<string, unknown>
): Promise<unknown> {
    switch (name) {
        case "dd_auth_status": {
            // status command outputs to stderr, not JSON - handle specially
            const { execDdCli } = await import("../core/executor.js");
            try {
                await execDdCli(["status"]);
                return { status: "authenticated", message: "dd-cli auth tokens are valid" };
            } catch (error) {
                const msg = error instanceof Error ? error.message : String(error);
                if (msg.includes("No auth") || msg.includes("not found")) {
                    return { status: "not_configured", action: "Run: dd-cli auth" };
                }
                if (msg.includes("expired") || msg.includes("failed")) {
                    return { status: "expired", action: "Run: dd-cli auth to refresh" };
                }
                // If it threw but no specific error, likely still worked (stderr output)
                return { status: "authenticated", message: "dd-cli connection ok" };
            }
        }

        case "dd_search_logs": {
            const query = args.query as string;
            const hours = (args.hours as number) || 24;
            const limit = (args.limit as number) || 50;
            const result = await execDdCliJson<LogResult>([
                "list",
                query,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
            return simplifyLogs(result);
        }

        case "dd_trace_logs": {
            const traceId = args.trace_id as string;
            const hours = (args.hours as number) || 24;
            const limit = (args.limit as number) || 200;
            const result = await execDdCliJson<LogResult>([
                "trace",
                traceId,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
            return simplifyLogs(result);
        }

        case "dd_fetch_log": {
            const logId = args.log_id as string;
            const sourceFragmentId = args.source_fragment_id as string;

            // Build compound ID from event_id + source_fragment_id
            // Extract just the UUID from source_fragment_id (before any "-synthetic" suffix)
            const uuid = sourceFragmentId.split("-synthetic")[0];

            // Build compound ID structure (reverse-engineered from Datadog web UI):
            // header + length byte + event_id + separator with '$' + uuid + trailer
            const header = Buffer.from([0x03, 0x00, 0x00, 0x01, 0x9b, 0x9e, 0x1e, 0x99, 0x2a, 0x5f, 0x80, 0x4b, 0xef, 0x00, 0x00, 0x00]);
            const eventIdLen = Buffer.from([logId.length]);
            const eventIdBuf = Buffer.from(logId, "ascii");
            const separator = Buffer.from([0x00, 0x00, 0x00, 0x24]); // 0x24 = '$'
            const uuidBuf = Buffer.from(uuid, "ascii");
            const trailer = Buffer.from([0x00, 0x0d, 0x16, 0x99]);

            const compoundId = Buffer.concat([header, eventIdLen, eventIdBuf, separator, uuidBuf, trailer]).toString("base64").replace(/=/g, "");

            const result = await execDdCliJson<{ result?: Record<string, unknown> }>(["fetch-one", compoundId]);
            // Return full result (user wants all details including errorDetails, custom fields, etc.)
            return result;
        }

        case "dd_top_values": {
            const query = args.query as string;
            const field = (args.field as string) || "service";
            const hours = (args.hours as number) || 24;
            const limit = (args.limit as number) || 10;
            return execDdCliJson([
                "top",
                query,
                "--field", field,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
        }

        case "dd_get_topology": {
            const env = (args.env as string) || "sandbox";
            const hours = (args.hours as number) || 1;
            const cliArgs = [
                "topology",
                "--env", env,
                "--hours", String(hours),
            ];
            if (args.service) {
                cliArgs.push("--service", args.service as string);
            }
            return execDdCliJson(cliArgs);
        }

        // =====================================================================
        // RUM (Real User Monitoring) Handlers
        // =====================================================================

        case "dd_rum_sessions": {
            const query = args.query as string;
            const hours = (args.hours as number) || 48;
            const limit = (args.limit as number) || 50;
            const result = await execDdCliJson<LogResult>([
                "rum", "sessions",
                query,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
            return simplifyLogs(result);
        }

        case "dd_rum_actions": {
            const query = args.query as string;
            const hours = (args.hours as number) || 24;
            const limit = (args.limit as number) || 50;
            const result = await execDdCliJson<LogResult>([
                "rum", "actions",
                query,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
            return simplifyLogs(result);
        }

        case "dd_rum_errors": {
            const query = args.query as string;
            const hours = (args.hours as number) || 24;
            const limit = (args.limit as number) || 50;
            const result = await execDdCliJson<LogResult>([
                "rum", "errors",
                query,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
            return simplifyLogs(result);
        }

        case "dd_rum_resources": {
            const query = args.query as string;
            const hours = (args.hours as number) || 24;
            const limit = (args.limit as number) || 50;
            const result = await execDdCliJson<LogResult>([
                "rum", "resources",
                query,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
            return simplifyLogs(result);
        }

        // =====================================================================
        // Field Discovery Handlers
        // =====================================================================

        case "dd_fields_search": {
            const keyword = args.keyword as string;
            const source = (args.source as string) || "logs";
            return execDdCliJson([
                "fields", "search",
                keyword,
                "--source", source,
            ]);
        }

        case "dd_fields_values": {
            const field = args.field as string;
            const source = (args.source as string) || "logs";
            const hours = (args.hours as number) || 24;
            const cliArgs = [
                "fields", "values",
                field,
                "--source", source,
                "--hours", String(hours),
            ];
            // Add optional query filter if provided
            if (args.query) {
                cliArgs.push("--query", args.query as string);
            }
            return execDdCliJson(cliArgs);
        }

        default:
            throw new Error(`Unknown tool: ${name}`);
    }
}

