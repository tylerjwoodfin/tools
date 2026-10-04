import assert from "node:assert/strict";
import test from "node:test";

import { ensureLocalModel, isModelCataloged, isModelLoaded, loadArgs } from "./ensure.js";

const PS_EMPTY = "No models are currently loaded.\n\nTo load a model, run:\n\n    lms load <model path>\n";
const PS_LOADED = `
IDENTIFIER   MODEL         SIZE     CONTEXT
gemma4-26b   gemma4-26b    15.78 GB 32768
`;
const LS_WITH_MODEL = `
LLM           PARAMS     ARCH      SIZE        DEVICE
gemma4-26b    26B-A4B    gemma4    16.95 GB    Local

EMBEDDING                               PARAMS    ARCH          SIZE
text-embedding-nomic-embed-text-v1.5              Nomic BERT    84.11 MB
`;

test("treats an empty LM Studio server as unloaded", () => {
  assert.equal(isModelLoaded(PS_EMPTY, "gemma4-26b"), false);
  assert.equal(isModelLoaded("", "gemma4-26b"), false);
});

test("recognizes the loaded identifier", () => {
  assert.equal(isModelLoaded(PS_LOADED, "gemma4-26b"), true);
  assert.equal(isModelLoaded(PS_LOADED, "other-model"), false);
});

test("finds the catalog key and ignores the embedding model", () => {
  assert.equal(isModelCataloged(LS_WITH_MODEL, "gemma4-26b"), true);
  assert.equal(isModelCataloged(LS_WITH_MODEL, "missing"), false);
});

test("loads with the context Cherry's config advertises", () => {
  assert.deepEqual(
    loadArgs({
      lmsBin: "lms",
      modelKey: "gemma4-26b",
      contextLength: 32768,
      identifier: "gemma4-26b",
    }),
    ["lms", "load", "gemma4-26b", "-y", "-c", "32768", "--identifier", "gemma4-26b"],
  );
});

test("skips load when the weights volume is unmounted", async () => {
  const result = await ensureLocalModel({
    exists: async () => false,
    run: async () => {
      throw new Error("should not call lms");
    },
  });
  assert.equal(result.status, "weights-missing");
});

test("does not reload a model that is already up", async () => {
  const calls = [];
  const result = await ensureLocalModel({
    exists: async () => true,
    run: async (args) => {
      calls.push(args[1]);
      return { code: 0, stdout: PS_LOADED, stderr: "" };
    },
  });
  assert.equal(result.status, "loaded");
  assert.deepEqual(calls, ["ps"]);
});

test("nudges a stale catalog, then loads", async () => {
  const calls = [];
  let nudged = false;
  const result = await ensureLocalModel({
    exists: async () => true,
    nudge: async () => {
      nudged = true;
    },
    run: async (args) => {
      calls.push(args[1]);
      if (args[1] === "ps") {
        return { code: 0, stdout: calls.filter((name) => name === "load").length ? PS_LOADED : PS_EMPTY, stderr: "" };
      }
      if (args[1] === "ls") {
        return { code: 0, stdout: nudged ? LS_WITH_MODEL : "EMBEDDING only\n", stderr: "" };
      }
      return { code: 0, stdout: "loaded", stderr: "" };
    },
  });
  assert.equal(nudged, true);
  assert.equal(result.status, "loaded");
  assert.deepEqual(calls, ["ps", "ls", "ls", "load", "ps"]);
});
