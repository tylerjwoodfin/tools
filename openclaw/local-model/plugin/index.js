import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

import { DEFAULTS, ensureLocalModel } from "./ensure.js";

let inflight = null;

function pluginConfig(api) {
  const entries = api?.config?.plugins?.entries?.["local-model"]?.config;
  return entries && typeof entries === "object" ? entries : {};
}

function optionsFrom(api) {
  const cfg = pluginConfig(api);
  return {
    identifier: typeof cfg.identifier === "string" && cfg.identifier.trim() ? cfg.identifier.trim() : DEFAULTS.identifier,
    modelKey: typeof cfg.modelKey === "string" && cfg.modelKey.trim() ? cfg.modelKey.trim() : DEFAULTS.modelKey,
    contextLength: Number.isInteger(cfg.contextLength) && cfg.contextLength >= 8192 ? cfg.contextLength : DEFAULTS.contextLength,
    weightsPath: typeof cfg.weightsPath === "string" && cfg.weightsPath.trim() ? cfg.weightsPath.trim() : DEFAULTS.weightsPath,
    modelLink: typeof cfg.modelLink === "string" && cfg.modelLink.trim() ? cfg.modelLink.trim() : DEFAULTS.modelLink,
  };
}

function ensure(api) {
  if (inflight) {
    return inflight;
  }
  inflight = ensureLocalModel(optionsFrom(api))
    .catch((err) => ({ status: "load-failed", detail: err?.message || String(err) }))
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

function logResult(api, result) {
  if (!result || result.status === "loaded" || result.status === "weights-missing") {
    if (result?.status === "weights-missing") {
      api.logger?.warn?.("local-model: Gemma weights are not mounted; leaving fallback in place");
    }
    return;
  }
  api.logger?.warn?.(`local-model: ${result.status}${result.detail ? ` (${result.detail})` : ""}`);
}

export default definePluginEntry({
  id: "local-model",
  name: "Local model",
  description: "Load Cherry's LM Studio model before a turn so chat does not fall back to OpenAI.",
  register(api) {
    api.on("gateway_start", () => {
      ensure(api).then((result) => logResult(api, result));
    });

    api.on("before_agent_run", async () => {
      const result = await ensure(api);
      logResult(api, result);
    });
  },
});
