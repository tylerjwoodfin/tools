import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

import {
  DEFAULT_MAX_ATTEMPTS,
  claimRetry,
  forgetRetry,
  isRetryableDeliveryFailure,
  normalizeTarget,
} from "./retry.js";

function pluginConfig(api) {
  const entries = api?.config?.plugins?.entries?.["delivery-retry"]?.config;
  return entries && typeof entries === "object" ? entries : {};
}

function maxAttempts(api) {
  const value = pluginConfig(api).maxAttempts;
  return Number.isInteger(value) && value >= 1 ? value : DEFAULT_MAX_ATTEMPTS;
}

function openclawBin() {
  return join(homedir(), "git", "tools", "openclaw", "openclaw-gateway");
}

function sendTelegram(target, message) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      openclawBin(),
      [
        "message",
        "send",
        "--channel",
        "telegram",
        "--target",
        target,
        "--json",
        "--message",
        message,
      ],
      { encoding: "utf8" },
    );
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error("telegram resend timed out"));
    }, 30_000);
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
        reject(new Error(stderr.trim() || stdout.trim() || `message send exited ${code}`));
        return;
      }
      resolve(stdout);
    });
  });
}

export default definePluginEntry({
  id: "delivery-retry",
  name: "Delivery retry",
  description:
    "Resend a Telegram reply when OpenClaw abandons an ambiguous network send.",
  register(api) {
    api.on("message_sent", (event, ctx) => {
      const content = String(event?.content || "").trim();
      const target = normalizeTarget(event?.to);
      const channel = String(ctx?.channelId || "telegram").toLowerCase();
      if (!content || !target || channel !== "telegram") return;

      if (event?.success === true) {
        forgetRetry(channel, target, content);
        return;
      }
      if (!isRetryableDeliveryFailure(event?.error)) return;

      const claimed = claimRetry({
        channel,
        target,
        content,
        now: Date.now(),
        max: maxAttempts(api),
      });
      if (!claimed) return;

      void sendTelegram(target, content)
        .then(() => {
          api.logger.info(
            `delivery-retry: resent Telegram message to ${target} (attempt ${claimed.attempt})`,
          );
        })
        .catch((err) => {
          api.logger.warn(
            `delivery-retry: resend to ${target} failed: ${err?.message || err}`,
          );
        });
    });
  },
});
