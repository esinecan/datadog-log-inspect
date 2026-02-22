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
        description: "Fetch full details of a single log entry including request bodies and custom metadata. Use compound_id from dd_search_logs or dd_trace_logs results.",
        inputSchema: {
            type: "object",
            properties: {
                compound_id: { type: "string", description: "The compound_id from a previous search result (AwAAA... base64 string)" },
            },
            required: ["compound_id"],
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
];


interface LogEvent {
    timestamp?: string;
    service?: string;
    status?: string;
    message?: string;
    trace_id?: string;
    id?: string;
    source_fragment_id?: string;
    compound_id?: string;
    custom?: unknown;
}

interface LogResult {
    result?: {
        events?: Array<{ event?: LogEvent }>;
    };
}

function simplifyLogEvent(event: Record<string, unknown>, compoundId?: string): LogEvent {
    return {
        timestamp: event.timestamp as string,
        service: event.service as string,
        status: event.status as string,
        message: ((event.message as string) || "").substring(0, 2000),
        trace_id: event.trace_id as string,
        id: event.id as string,
        source_fragment_id: event.source_fragment_id as string,
        compound_id: compoundId,
        custom: event.custom,
    };
}

function simplifyLogs(result: LogResult): { count: number; events: LogEvent[] } {
    const events = result.result?.events || [];
    const simplified = events.map((e) => {
        const raw = e as unknown as Record<string, unknown>;
        // compound_id is the top-level `id` on each list event; used for dd_fetch_log
        const compoundId = raw.id as string | undefined;
        return simplifyLogEvent(raw.event as Record<string, unknown> || {}, compoundId);
    });
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
            // compound_id is the `compound_id` field from dd_search_logs / dd_trace_logs results
            const compoundId = args.compound_id as string;
            const result = await execDdCliJson<{ result?: Record<string, unknown> }>(["fetch-one", compoundId]);
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

        default:
            throw new Error(`Unknown tool: ${name}`);
    }
}

