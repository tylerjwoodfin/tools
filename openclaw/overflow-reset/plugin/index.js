import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

const DEFAULT_MIN_MESSAGES = 6;
const DEFAULT_COOLDOWN_SECONDS = 120;
const OVERFLOW_RE = /context overflow|too large for the model|exceed_context_size|exceeds the available context|request_too_large|context length exceeded/i;
const SKIP_TRIGGERS = new Set(["heartbeat", "cron"]);

const lastPromptBySession = new Map();
const lastResetAtBySession = new Map();
const pendingResetBySession = new Set();

function pluginConfig(api) {
  const entries = api?.config?.plugins?.entries?.["overflow-reset"]?.config;
  return entries && typeof entries === "object" ? entries : {};
}

function minMessages(api) {
  const value = pluginConfig(api).minMessages;
  return Number.isInteger(value) && value >= 2 ? value : DEFAULT_MIN_MESSAGES;
}

function cooldownMs(api) {
  const value = pluginConfig(api).cooldownSeconds;
  const seconds = Number.isInteger(value) && value >= 10 ? value : DEFAULT_COOLDOWN_SECONDS;
  return seconds * 1000;
}

function openclawBin() {
  return join(homedir(), "git", "tools", "openclaw", "openclaw-gateway");
}

function isOverflowError(text) {
  return Boolean(text && OVERFLOW_RE.test(String(text)));
}

function collectText(value, into = []) {
  if (typeof value === "string") {
    into.push(value);
    return into;
  }
  if (!value || typeof value !== "object") {
    return into;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      collectText(item, into);
    }
    return into;
  }
  for (const key of ["error", "message", "text", "content"]) {
    if (key in value) {
      collectText(value[key], into);
    }
  }
  return into;
}

function eventLooksLikeOverflow(event) {
  if (event?.success === true) {
    return false;
  }
  return collectText(event).some(isOverflowError);
}

function gatewayCallCli(method, params) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      openclawBin(),
      ["gateway", "call", method, "--json", "--params", JSON.stringify(params)],
      { encoding: "utf8" },
    );
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error(`${method} timed out`));
    }, 20_000);
    child.stdout?.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr?.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(stderr.trim() || stdout.trim() || `${method} exited ${code}`));
        return;
      }
      const start = stdout.indexOf("{");
      if (start < 0) {
        resolve(stdout);
        return;
      }
      try {
        resolve(JSON.parse(stdout.slice(start)));
      } catch {
        resolve(stdout);
      }
    });
  });
}

async function gatewayCall(api, method, params) {
  try {
    if (await api.runtime?.gateway?.isAvailable?.()) {
      return await api.runtime.gateway.request(method, params);
    }
  } catch {
    // External plugins cannot always use the in-process Gateway client.
  }
  return gatewayCallCli(method, params);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default definePluginEntry({
  id: "overflow-reset",
  name: "Overflow reset",
  description:
    "When context overflow recovery is exhausted, start a fresh session and retry the last user message once.",
  register(api) {
    api.on("before_agent_run", (event, ctx) => {
      const sessionKey = ctx?.sessionKey;
      const prompt = typeof event?.prompt === "string" ? event.prompt.trim() : "";
      if (!sessionKey || !prompt) {
        return;
      }
      if (SKIP_TRIGGERS.has(String(ctx?.trigger || ""))) {
        return;
      }
      lastPromptBySession.set(sessionKey, {
        prompt,
        messageCount: Array.isArray(event?.messages) ? event.messages.length : 0,
        at: Date.now(),
      });
    });

    api.on("message_sending", (event, ctx) => {
      const content = String(event?.content || "");
      if (!isOverflowError(content)) {
        return;
      }
      const sessionKey = ctx?.sessionKey;
      const cached = sessionKey ? lastPromptBySession.get(sessionKey) : null;
      if (!sessionKey || !cached || cached.messageCount < minMessages(api)) {
        return;
      }
      pendingResetBySession.add(sessionKey);
      return {
        content:
          "Context was too large for the local model. Starting a fresh session and retrying…",
      };
    });

    api.on("agent_end", async (event, ctx) => {
      const sessionKey = ctx?.sessionKey;
      if (!sessionKey || SKIP_TRIGGERS.has(String(ctx?.trigger || ""))) {
        return;
      }
      if (!eventLooksLikeOverflow(event) && !pendingResetBySession.has(sessionKey)) {
        return;
      }

      const cached = lastPromptBySession.get(sessionKey);
      const messageCount = Array.isArray(event?.messages)
        ? event.messages.length
        : cached?.messageCount || 0;
      if (messageCount < minMessages(api)) {
        api.logger.info(
          `overflow-reset: skip ${sessionKey} (only ${messageCount} messages; system prompt probably does not fit)`,
        );
        pendingResetBySession.delete(sessionKey);
        return;
      }

      const now = Date.now();
      const lastReset = lastResetAtBySession.get(sessionKey) || 0;
      if (now - lastReset < cooldownMs(api)) {
        api.logger.info(`overflow-reset: skip ${sessionKey} (cooldown)`);
        pendingResetBySession.delete(sessionKey);
        return;
      }

      const prompt = cached?.prompt;
      if (!prompt || prompt.startsWith("/")) {
        api.logger.info(`overflow-reset: skip ${sessionKey} (no replayable prompt)`);
        pendingResetBySession.delete(sessionKey);
        return;
      }

      pendingResetBySession.add(sessionKey);
      lastResetAtBySession.set(sessionKey, now);
      try {
        await gatewayCall(api, "sessions.reset", { key: sessionKey, reason: "new" });
        await sleep(400);
        await gatewayCall(api, "sessions.send", { key: sessionKey, message: prompt });
        api.logger.info(`overflow-reset: reset and retried ${sessionKey}`);
      } catch (err) {
        api.logger.warn(`overflow-reset: failed for ${sessionKey}: ${err?.message || err}`);
      } finally {
        setTimeout(() => pendingResetBySession.delete(sessionKey), 15_000);
      }
    });
  },
});
