#!/usr/bin/env node

/**
 * datadog-mcp: MCP server wrapping dd-cli for Datadog queries
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
    CallToolRequestSchema,
    ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { TOOLS, handleToolCall } from "../tools/index.js";
import { checkDdCli } from "../core/executor.js";

async function main() {
    // Verify dd-cli is available
    const ddCheck = await checkDdCli();
    if (!ddCheck.available) {
        console.error(`[datadog-mcp] Error: ${ddCheck.error}`);
        process.exit(1);
    }
    console.error("[datadog-mcp] dd-cli authenticated");

    const server = new Server(
        {
            name: "datadog-mcp",
            version: "0.1.0",
        },
        {
            capabilities: {
                tools: {},
            },
        }
    );

    server.setRequestHandler(ListToolsRequestSchema, async () => ({
        tools: TOOLS,
    }));

    server.setRequestHandler(CallToolRequestSchema, async (request) => {
        const { name, arguments: args } = request.params;
        console.error(`[datadog-mcp] Tool called: ${name}`);

        try {
            const result = await handleToolCall(name, args as Record<string, unknown>);
            return {
                content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
            };
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            console.error(`[datadog-mcp] Error: ${errorMessage}`);
            return {
                content: [{ type: "text", text: JSON.stringify({ error: errorMessage }) }],
                isError: true,
            };
        }
    });

    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("[datadog-mcp] Server running on stdio");

    process.on("SIGINT", () => {
        console.error("[datadog-mcp] Shutting down...");
        process.exit(0);
    });
}

main().catch((error) => {
    console.error("[datadog-mcp] Fatal error:", error);
    process.exit(1);
});
