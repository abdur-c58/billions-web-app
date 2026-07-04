import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cloudflared = path.join(os.homedir(), ".cloudflared", "cloudflared.exe");
const tunnelUrlRe = /https:\/\/[a-z0-9-]+\.trycloudflare\.com/i;

let printedTunnel = false;
const children = [];

function createLineReader(onLine) {
  let buffer = "";
  return (chunk) => {
    buffer += chunk.toString();
    const parts = buffer.split(/\r?\n/);
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      onLine(line);
    }
  };
}

function maybePrintTunnelUrl(line) {
  const match = line.match(tunnelUrlRe);
  if (!match || printedTunnel) return;
  printedTunnel = true;
  const url = match[0];
  console.log("");
  console.log("\x1b[32m==================================================");
  console.log(`  Cloudflare tunnel: ${url}`);
  console.log("  Paste in app: Backend Connect");
  console.log("==================================================\x1b[0m");
  console.log("");
}

function pipe(name, colorCode, proc) {
  const prefix = (line) => `\x1b[${colorCode}m[${name}]\x1b[0m ${line}`;

  const onLine = (line) => {
    if (!line.trim()) return;
    maybePrintTunnelUrl(line);
    console.log(prefix(line));
  };

  proc.stdout.on("data", createLineReader(onLine));
  proc.stderr.on("data", createLineReader(onLine));
}

function shutdown() {
  for (const child of children) {
    if (!child.killed) {
      child.kill("SIGTERM");
    }
  }
}

function start(name, command, args, options = {}) {
  const proc = spawn(command, args, {
    cwd: root,
    shell: process.platform === "win32",
    stdio: ["ignore", "pipe", "pipe"],
    ...options,
  });
  children.push(proc);
  proc.on("exit", (code, signal) => {
    if (signal) return;
    shutdown();
    process.exit(code ?? 0);
  });
  return proc;
}

if (!fs.existsSync(cloudflared)) {
  console.error(`cloudflared not found at ${cloudflared}`);
  process.exit(1);
}

console.log("\nStarting Billions backend + Cloudflare tunnel...\n");

const api = start("api", "npm", ["run", "dev:api"]);
const tunnel = start("tunnel", cloudflared, ["tunnel", "--url", "http://127.0.0.1:8766"]);

pipe("api", "32", api);
pipe("tunnel", "36", tunnel);

process.on("SIGINT", () => {
  shutdown();
  process.exit(0);
});
process.on("SIGTERM", () => {
  shutdown();
  process.exit(0);
});
