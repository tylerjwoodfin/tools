#!/usr/bin/env node
import { ensureLocalModel } from "../plugin/ensure.js";

const result = await ensureLocalModel();
if (result.status === "loaded") {
  console.log(`loaded ${result.identifier}`);
  process.exit(0);
}
if (result.status === "weights-missing") {
  console.log("weights not mounted; skipped");
  process.exit(0);
}
console.error(`${result.status}${result.detail ? `: ${result.detail}` : ""}`);
process.exit(1);
