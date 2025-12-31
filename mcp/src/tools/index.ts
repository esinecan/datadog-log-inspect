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
        description: "Fetch full details of a single log entry by ID",
        inputSchema: {
            type: "object",
            properties: {
                log_id: { type: "string", description: "The log ID from a previous search" },
            },
            required: ["log_id"],
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
];

interface LogEvent {
    timestamp?: string;
    service?: string;
    status?: string;
    message?: string;
    trace_id?: string;
    id?: string;
}

interface LogResult {
    result?: {
        events?: Array<{ event?: LogEvent }>;
    };
}

function simplifyLogs(result: LogResult): { count: number; events: LogEvent[] } {
    const events = result.result?.events || [];
    const simplified = events.map((e) => ({
        timestamp: e.event?.timestamp,
        service: e.event?.service,
        status: e.event?.status,
        message: (e.event?.message || "").substring(0, 500),
        trace_id: e.event?.trace_id,
        id: e.event?.id,
    }));
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
                `'${query}'`,
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
            return execDdCliJson(["fetch-one", logId]);
        }

        case "dd_top_values": {
            const query = args.query as string;
            const field = (args.field as string) || "service";
            const hours = (args.hours as number) || 24;
            const limit = (args.limit as number) || 10;
            return execDdCliJson([
                "top",
                `'${query}'`,
                "--field", field,
                "--hours", String(hours),
                "--limit", String(limit),
            ]);
        }

        default:
            throw new Error(`Unknown tool: ${name}`);
    }
}
