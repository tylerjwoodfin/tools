import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function pluginConfig(api) {
  const entries = api?.config?.plugins?.entries?.words?.config;
  return entries && typeof entries === "object" ? entries : {};
}

function resolveCli(api) {
  const cfg = pluginConfig(api);
  if (typeof cfg.cliPath === "string" && cfg.cliPath.trim()) {
    return cfg.cliPath.trim();
  }
  return join(homedir(), "git", "tools", "openclaw", "words", "scripts", "words_cli.py");
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

function runWords(api, args) {
  const cli = resolveCli(api);
  const python = resolvePython(api);
  const result = spawnSync(python, [cli, "--json", ...args], {
    encoding: "utf8",
    timeout: 90_000,
    env: {
      ...process.env,
      WORDS_CLI_INTERNAL: "1",
    },
  });
  const stdout = (result.stdout || "").trim();
  const stderr = (result.stderr || "").trim();
  if (result.error) {
    return {
      ok: false,
      action: "error",
      message: `words cli failed to start (${python} ${cli}): ${result.error.message}`,
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

function extractWordsCommand(text) {
  const t = (text || "").trim();
  if (!t) return null;
  const match = t.match(/(?:^|\n)\s*(\/(?:words|recall)(?:@[^\s]+)?(?:[^\n]*))\s*$/i);
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
  id: "words",
  name: "Word recall",
  description:
    "Quizzes definitions from words_to_remember.md on /words and on a diary-like cadence.",
  register(api) {
    api.registerCommand({
      name: "words",
      description: "Practice a word, add one, or list the recall deck",
      acceptsArgs: true,
      handler: async (ctx) => {
        const args = (ctx.args || "").trim();
        const result = runWords(api, ["handle", "--force", args ? `/words ${args}` : "/words"]);
        return { text: extractReplyText(result) };
      },
    });

    api.on(
      "before_agent_reply",
      (event, ctx) => {
        if (process.env.WORDS_CLI_INTERNAL === "1") {
          return;
        }
        const body = (event.cleanedBody || event.body || "").trim();
        if (!body) {
          return;
        }

        const wordsCmd = extractWordsCommand(body);
        if (wordsCmd) {
          const result = runWords(api, ["handle", "--force", wordsCmd]);
          return {
            handled: true,
            reply: { text: extractReplyText(result) },
          };
        }

        if (!isTelegramTurn(ctx)) {
          return;
        }

        const result = runWords(api, ["handle", body]);
        if (!result.ok) {
          return {
            handled: true,
            reply: { text: extractReplyText(result) },
          };
        }
        if (result.action === "skip" || !result.message) {
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
