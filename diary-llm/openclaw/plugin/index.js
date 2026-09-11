import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { spawnSync } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

function pluginConfig(api) {
  const entries = api?.config?.plugins?.entries?.["diary-llm"]?.config;
  return entries && typeof entries === "object" ? entries : {};
}

function resolveCli(api) {
  const cfg = pluginConfig(api);
  if (typeof cfg.cliPath === "string" && cfg.cliPath.trim()) {
    return cfg.cliPath.trim();
  }
  return join(homedir(), "git", "tools", "diary-llm", ".venv", "bin", "diary-llm");
}

function resolveConfigPath(api) {
  const cfg = pluginConfig(api);
  if (typeof cfg.configPath === "string" && cfg.configPath.trim()) {
    return cfg.configPath.trim();
  }
  return null;
}

function runDiary(api, args) {
  const cli = resolveCli(api);
  const configPath = resolveConfigPath(api);
  const fullArgs = [];
  if (configPath) {
    fullArgs.push("--config", configPath);
  }
  fullArgs.push("--json", ...args);

  const result = spawnSync(cli, fullArgs, {
    encoding: "utf8",
    // Keep this bounded so a stuck model cannot wedge the Gateway turn forever.
    timeout: 90_000,
    env: {
      ...process.env,
      // Prevent recursive diary handling if diary-llm shells out to OpenClaw.
      DIARY_LLM_INTERNAL: "1",
    },
  });

  const stdout = (result.stdout || "").trim();
  const stderr = (result.stderr || "").trim();

  if (result.error) {
    return {
      ok: false,
      exitCode: result.status ?? 1,
      message: `diary-llm failed to start (${cli}): ${result.error.message}`,
      raw: stderr || stdout,
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
    ok: result.status === 0,
    exitCode: result.status ?? 1,
    parsed,
    message:
      (parsed && typeof parsed === "object" && !Array.isArray(parsed) && parsed.message) ||
      stdout ||
      stderr ||
      null,
    raw: stdout || stderr,
  };
}

function isDiaryCommand(text) {
  return Boolean(extractDiaryCommand(text));
}

function extractDiaryCommand(text) {
  const t = (text || "").trim();
  if (!t) return null;
  const lower = t.toLowerCase();
  if (lower === "/diary" || lower.startsWith("/diary ")) {
    return t.split(/\r?\n/)[0].trim();
  }
  // Skill-injected turns often look like "...\nUser request:\n/diary"
  const match = t.match(/(?:^|\n)\s*(\/diary(?:[^\n]*))\s*$/i);
  return match ? match[1].trim() : null;
}

function isTelegramTurn(ctx) {
  const channel = String(ctx?.channel || ctx?.messageProvider || "").toLowerCase();
  return channel === "telegram";
}

function statusIsActive(api) {
  const result = runDiary(api, ["status"]);
  if (result.parsed && typeof result.parsed === "object") {
    return Boolean(result.parsed.active);
  }
  return false;
}

function extractReplyText(result) {
  if (result?.parsed && typeof result.parsed === "object" && !Array.isArray(result.parsed)) {
    if (typeof result.parsed.message === "string" && result.parsed.message.trim()) {
      return result.parsed.message.trim();
    }
  }
  return (result?.message || result?.raw || "OK").toString();
}

export default definePluginEntry({
  id: "diary-llm",
  name: "Diary LLM",
  description:
    "Routes /diary and active diary Telegram turns through diary-llm without treating normal chats as journal entries.",
  register(api) {
    api.registerCommand({
      name: "diary",
      description: "Start, continue, or finish a conversational diary session",
      acceptsArgs: true,
      handler: async (ctx) => {
        const args = (ctx.args || "").trim().toLowerCase();
        if (!args || args === "start") {
          const result = runDiary(api, ["start"]);
          return { text: extractReplyText(result) };
        }
        if (args === "done" || args === "end" || args === "finish") {
          const result = runDiary(api, ["done"]);
          return { text: extractReplyText(result) };
        }
        if (args === "status") {
          const result = runDiary(api, ["status"]);
          if (result.parsed?.active) {
            return {
              text:
                `Active diary session ${result.parsed.session_id}\n` +
                `Prompt: ${result.parsed.initial_prompt || "(none)"}`,
            };
          }
          return { text: "No active diary session." };
        }
        runDiary(api, ["start"]);
        const result = runDiary(api, ["reply", ctx.args.trim()]);
        return { text: extractReplyText(result) };
      },
    });

    api.on(
      "before_agent_reply",
      (event, ctx) => {
        if (process.env.DIARY_LLM_INTERNAL === "1") {
          return;
        }

        const body = (event.cleanedBody || event.body || "").trim();
        if (!body) {
          return;
        }

        const diaryCmd = extractDiaryCommand(body);
        // Always claim /diary* — do not let the general agent roleplay journaling.
        if (diaryCmd) {
          const result = runDiary(api, ["handle", diaryCmd]);
          return {
            handled: true,
            reply: { text: extractReplyText(result) },
          };
        }

        // Active-session follow-ups: Telegram only.
        if (!isTelegramTurn(ctx)) {
          return;
        }

        if (!statusIsActive(api)) {
          return;
        }

        const result = runDiary(api, ["reply", body]);
        if (result.exitCode === 2 || result.parsed?.action === "not_diary") {
          return;
        }
        return {
          handled: true,
          reply: {
            text: extractReplyText(result),
          },
        };
      },
      { eligibleTriggers: ["user"] },
    );
  },
});
