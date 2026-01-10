/**
 * dd-cli executor - wrapper for running dd-cli commands
 */

import { exec } from "child_process";
import { promisify } from "util";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const execAsync = promisify(exec);

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Path to dd-cli in parent directory
const DD_CLI_PATH = resolve(__dirname, "../../../dd-cli");
const PYTHONPATH = resolve(__dirname, "../../..");

const TIMEOUT_MS = parseInt(process.env.DD_MCP_TIMEOUT_MS || "60000", 10);
const DEBUG = process.env.DD_MCP_DEBUG === "true";

/**
 * Check if dd-cli is available and authenticated
 */
export async function checkDdCli(): Promise<{ available: boolean; error?: string }> {
    try {
        const { stdout } = await execAsync(`python3 ${DD_CLI_PATH} status`, {
            timeout: 10000,
            env: { ...process.env, PYTHONPATH },
        });
        return { available: true };
    } catch (error: unknown) {
        const execError = error as { stderr?: string; message: string };
        if (execError.stderr?.includes("No auth")) {
            return { available: false, error: "dd-cli not authenticated. Run: dd-cli auth" };
        }
        return { available: false, error: execError.stderr || execError.message };
    }
}

/**
 * Execute a dd-cli command and return raw stdout
 */
export async function execDdCli(args: string[]): Promise<string> {
    // Shell-quote each argument to handle spaces and special chars
    const quotedArgs = args.map(arg => {
        // If arg contains spaces, special chars, or glob chars (*?[]), quote it
        if (/[\s"'$`\\*?[\]]/.test(arg)) {
            // Escape single quotes and wrap in single quotes
            return `'${arg.replace(/'/g, "'\\''")}'`;
        }
        return arg;
    });
    const command = `python3 ${DD_CLI_PATH} ${quotedArgs.join(" ")}`;

    if (DEBUG) {
        console.error(`[datadog-mcp] Executing: ${command}`);
    }

    try {
        const { stdout, stderr } = await execAsync(command, {
            timeout: TIMEOUT_MS,
            maxBuffer: 10 * 1024 * 1024,
            env: { ...process.env, PYTHONPATH },
        });

        if (DEBUG && stderr) {
            console.error(`[datadog-mcp] stderr: ${stderr}`);
        }

        return stdout;
    } catch (error: unknown) {
        const execError = error as { stderr?: string; message: string };
        throw new Error(execError.stderr || execError.message);
    }
}

/**
 * Execute dd-cli and parse JSON output
 */
export async function execDdCliJson<T>(args: string[]): Promise<T> {
    const stdout = await execDdCli(args);

    try {
        return JSON.parse(stdout) as T;
    } catch {
        throw new Error(`Failed to parse JSON: ${stdout.substring(0, 200)}`);
    }
}
