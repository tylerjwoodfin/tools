import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function pluginConfig(api) {
  const entries = api?.config?.plugins?.entries?.food?.config;
  return entries && typeof entries === "object" ? entries : {};
}

function resolveCli(api) {
  const cfg = pluginConfig(api);
  if (typeof cfg.cliPath === "string" && cfg.cliPath.trim()) {
    return cfg.cliPath.trim();
  }
  return join(homedir(), "git", "tools", "openclaw", "food", "scripts", "food_cli.py");
}

function resolvePython(api) {
  const cfg = pluginConfig(api);
  if (typeof cfg.pythonPath === "string" && cfg.pythonPath.trim()) {
    return cfg.pythonPath.trim();
  }
  const brew = "/opt/homebrew/bin/python3";
  if (existsSync(brew)) {
    return brew;
  }
  return "python3";
}

function runFood(api, args) {
  const cli = resolveCli(api);
  const python = resolvePython(api);
  const result = spawnSync(python, [cli, "--json", ...args], {
    encoding: "utf8",
    timeout: 90_000,
    env: {
      ...process.env,
      FOOD_CLI_INTERNAL: "1",
    },
  });
  const stdout = (result.stdout || "").trim();
  const stderr = (result.stderr || "").trim();
  if (result.error) {
    return {
      ok: false,
      action: "error",
      message: `food cli failed to start (${python} ${cli}): ${result.error.message}`,
    };
  }
  let parsed = null;
  if (stdout) {
    try {
      parsed = JSON.parse(stdout);
    } catch {
      parsed = null;
    }
  }
  return {
    ok: result.status === 0 && (parsed?.ok ?? true),
    action: parsed?.action || (result.status === 0 ? "ok" : "error"),
    message: parsed?.message || stdout || stderr || null,
    parsed,
  };
}

function extractFoodCommand(text) {
  const t = (text || "").trim();
  if (!t) return null;
  const lower = t.toLowerCase();
  if (lower === "/food" || lower.startsWith("/food ") || lower.startsWith("/food@")) {
    return t.split(/\r?\n/)[0].trim();
  }
  const match = t.match(/(?:^|\n)\s*(\/food(?:[^\n]*))\s*$/i);
  return match ? match[1].trim() : null;
}

function isTelegramTurn(ctx) {
  const channel = String(ctx?.channel || ctx?.messageProvider || "").toLowerCase();
  return channel === "telegram";
}

function extractReplyText(result) {
  if (typeof result?.message === "string" && result.message.trim()) {
    return result.message.trim();
  }
  return "OK";
}

export default definePluginEntry({
  id: "food",
  name: "Food log",
  description:
    "Routes /food and reminder follow-ups through foodlog without using the main session model.",
  register(api) {
    api.registerCommand({
      name: "food",
      description: "Log food from any phrasing, or show today's log",
      acceptsArgs: true,
      handler: async (ctx) => {
        const args = (ctx.args || "").trim();
        const result = args
          ? runFood(api, ["handle", "--force", args])
          : runFood(api, ["handle", "--force", ""]);
        return { text: extractReplyText(result) };
      },
    });

    api.on(
      "before_agent_reply",
      (event, ctx) => {
        if (process.env.FOOD_CLI_INTERNAL === "1") {
          return;
        }
        const body = (event.cleanedBody || event.body || "").trim();
        if (!body) {
          return;
        }

        const foodCmd = extractFoodCommand(body);
        if (foodCmd) {
          const args = foodCmd.replace(/^\/food(?:@\S+)?\s*/i, "").trim();
          const result = args
            ? runFood(api, ["handle", "--force", args])
            : runFood(api, ["handle", "--force", ""]);
          return {
            handled: true,
            reply: { text: extractReplyText(result) },
          };
        }

        if (!isTelegramTurn(ctx)) {
          return;
        }

        const result = runFood(api, ["handle", body]);
        if (!result.ok) {
          return {
            handled: true,
            reply: { text: extractReplyText(result) },
          };
        }
        if (result.action === "not_food" || result.action === "skip" || !result.message) {
          return;
        }
        return {
          handled: true,
          reply: { text: extractReplyText(result) },
        };
      },
      { eligibleTriggers: ["user"] },
    );
  },
});
