/**
 * Generates a stable per-browser/per-device visitor ID using the open-source
 * FingerprintJS library. The ID is cached in localStorage so subsequent calls
 * are instant and survive page reloads.
 *
 * Used at registration to enforce "one account per device" — prevents users
 * from spinning up multiple emails after their trial expires.
 */
import FingerprintJS from "@fingerprintjs/fingerprintjs";

const CACHE_KEY = "co_device_fp_v1";

let _agentPromise = null;

export async function getDeviceFingerprint() {
  // Cached → fast path
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached && cached.length >= 16) return cached;
  } catch {
    // localStorage unavailable (private mode / disabled storage) — fall through
  }

  try {
    if (!_agentPromise) _agentPromise = FingerprintJS.load();
    const agent = await _agentPromise;
    const result = await agent.get();
    const fp = result.visitorId;
    try {
      localStorage.setItem(CACHE_KEY, fp);
    } catch {
      // ignore storage failures
    }
    return fp;
  } catch {
    // Fingerprinting failed — return null so register flow continues without it.
    return null;
  }
}
