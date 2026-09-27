import assert from "node:assert/strict";
import test from "node:test";

import {
  claimRetry,
  forgetRetry,
  isRetryableDeliveryFailure,
  normalizeTarget,
} from "./retry.js";

test("retries the ambiguous Telegram drop", () => {
  assert.equal(
    isRetryableDeliveryFailure(
      "delivery state is unknown_after_send; refusing blind replay without adapter reconciliation",
    ),
    true,
  );
  assert.equal(
    isRetryableDeliveryFailure("Network request for 'sendMessage' failed!"),
    true,
  );
});

test("leaves permanent Telegram failures alone", () => {
  assert.equal(isRetryableDeliveryFailure("Forbidden: bot was blocked by the user"), false);
  assert.equal(isRetryableDeliveryFailure("chat not found"), false);
  assert.equal(isRetryableDeliveryFailure(""), false);
});

test("strips a telegram target prefix", () => {
  assert.equal(normalizeTarget("telegram:8974380881"), "8974380881");
  assert.equal(normalizeTarget(" 8974380881 "), "8974380881");
});

test("claims one retry per text inside the debounce window", () => {
  const args = {
    channel: "telegram",
    target: "1",
    content: "closing line",
    max: 3,
  };
  const first = claimRetry({ ...args, now: 10_000 });
  const second = claimRetry({ ...args, now: 12_000 });
  const third = claimRetry({ ...args, now: 20_000 });
  assert.equal(first?.attempt, 1);
  assert.equal(second, null);
  assert.equal(third?.attempt, 2);
  forgetRetry("telegram", "1", "closing line");
});
