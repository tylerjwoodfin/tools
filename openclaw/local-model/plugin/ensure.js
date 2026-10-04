import { spawn } from "node:child_process";
import { access, rename } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

export const DEFAULTS = {
  identifier: "gemma4-26b",
  modelKey: "gemma4-26b",
  contextLength: 32768,
  weightsPath: "/Volumes/2TB/ai-models/gemma4-26b/gemma-4-26B-A4B-it-Q4_K_M.gguf",
  modelLink: join(homedir(), ".lmstudio/models/ollama/gemma4-26b"),
  lmsBin: join(homedir(), ".lmstudio/bin/lms"),
  loadTimeoutMs: 180_000,
};

export function isModelLoaded(psText, identifier) {
  if (!psText || /no models are currently loaded/i.test(psText)) {
    return false;
  }
  const wanted = String(identifier || "").trim().toLowerCase();
  if (!wanted) {
    return false;
  }
  return psText.split(/\r?\n/).some((line) => firstCell(line) === wanted);
}

export function isModelCataloged(lsText, modelKey) {
  const wanted = String(modelKey || "").trim().toLowerCase();
  if (!wanted || !lsText) {
    return false;
  }
  return lsText.split(/\r?\n/).some((line) => firstCell(line) === wanted);
}

export function loadArgs(options) {
  const cfg = { ...DEFAULTS, ...options };
  return [
    cfg.lmsBin,
    "load",
    cfg.modelKey,
    "-y",
    "-c",
    String(cfg.contextLength),
    "--identifier",
    cfg.identifier,
  ];
}

function firstCell(line) {
  return String(line || "").trim().split(/\s+/)[0]?.toLowerCase() || "";
}

export function runCommand(args, { timeoutMs = DEFAULTS.loadTimeoutMs } = {}) {
  return new Promise((resolve) => {
    const child = spawn(args[0], args.slice(1), { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      resolve({
        code: 124,
        stdout,
        stderr: `${stderr}\ncommand timed out`.trim(),
      });
    }, timeoutMs);
    child.stdout?.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr?.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      resolve({ code: 127, stdout, stderr: err.message });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

async function pathExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

export async function nudgeModelLink(linkPath, sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))) {
  const parked = `${linkPath}.off`;
  await rename(linkPath, parked);
  try {
    await sleep(400);
  } finally {
    await rename(parked, linkPath);
  }
  await sleep(1200);
}

/**
 * Make sure the local Cherry model is loaded in LM Studio.
 * A missing weights file is not an error: OpenClaw may fall back.
 */
export async function ensureLocalModel(options = {}) {
  const cfg = { ...DEFAULTS, ...options };
  const run = cfg.run || runCommand;
  const sleep = cfg.sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
  const nudge = cfg.nudge || ((linkPath) => nudgeModelLink(linkPath, sleep));
  const exists = cfg.exists || pathExists;

  if (!(await exists(cfg.weightsPath))) {
    return { status: "weights-missing", identifier: cfg.identifier };
  }

  const listed = await run([cfg.lmsBin, "ps"], { timeoutMs: 20_000 });
  if (listed.code === 0 && isModelLoaded(listed.stdout, cfg.identifier)) {
    return { status: "loaded", identifier: cfg.identifier };
  }

  const catalog = await run([cfg.lmsBin, "ls"], { timeoutMs: 20_000 });
  let cataloged = catalog.code === 0 && isModelCataloged(catalog.stdout, cfg.modelKey);
  if (!cataloged && (await exists(cfg.modelLink))) {
    await nudge(cfg.modelLink);
    const again = await run([cfg.lmsBin, "ls"], { timeoutMs: 20_000 });
    cataloged = again.code === 0 && isModelCataloged(again.stdout, cfg.modelKey);
  }
  if (!cataloged) {
    return {
      status: "not-cataloged",
      identifier: cfg.identifier,
      detail: (catalog.stderr || catalog.stdout || "model is not in lms ls").trim(),
    };
  }

  const loaded = await run(loadArgs(cfg), { timeoutMs: cfg.loadTimeoutMs });
  const combined = `${loaded.stdout}\n${loaded.stderr}`;
  const ps = await run([cfg.lmsBin, "ps"], { timeoutMs: 20_000 });
  if (ps.code === 0 && isModelLoaded(ps.stdout, cfg.identifier)) {
    return { status: "loaded", identifier: cfg.identifier };
  }
  if (/already exists/i.test(combined) && isModelLoaded(ps.stdout, cfg.identifier)) {
    return { status: "loaded", identifier: cfg.identifier };
  }
  return {
    status: "load-failed",
    identifier: cfg.identifier,
    detail: combined.trim().slice(-500) || `lms load exited ${loaded.code}`,
  };
}
