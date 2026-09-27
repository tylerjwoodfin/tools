const DEFAULT_MAX_ATTEMPTS = 3;
const SAME_TEXT_WINDOW_MS = 8_000;

// OpenClaw treats a Telegram network error as "maybe delivered" and then
// refuses to replay it, which drops the reply. These are the errors from that
// path, plus the original transport failure if it is what the hook reports.
const RETRYABLE_ERROR =
  /network request for|unknown_after_send|refusing blind replay|ECONNRESET|ETIMEDOUT|EAI_AGAIN|ENOTFOUND|socket hang up|fetch failed|und_err/i;

const recentByKey = new Map();

export function isRetryableDeliveryFailure(error) {
  const text = String(error || "").trim();
  if (!text) return false;
  return RETRYABLE_ERROR.test(text);
}

export function normalizeTarget(to) {
  return String(to || "")
    .trim()
    .replace(/^telegram:/i, "");
}

export function deliveryKey(channel, target, content) {
  return `${channel}\n${target}\n${content}`;
}

export function claimRetry({ channel, target, content, now, max = DEFAULT_MAX_ATTEMPTS }) {
  const key = deliveryKey(channel, target, content);
  const state = recentByKey.get(key) || { attempts: 0, lastAt: 0 };
  if (state.attempts >= max) return null;
  if (now - state.lastAt < SAME_TEXT_WINDOW_MS) return null;
  state.attempts += 1;
  state.lastAt = now;
  recentByKey.set(key, state);
  return { key, attempt: state.attempts };
}

export function forgetRetry(channel, target, content) {
  recentByKey.delete(deliveryKey(channel, target, content));
}

export { DEFAULT_MAX_ATTEMPTS };
