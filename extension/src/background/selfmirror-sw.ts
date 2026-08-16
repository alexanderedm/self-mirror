/**
 * SelfMirror — Background Service Worker
 *
 * Simplified event collector:
 * - Tracks tab URL/title changes and reports to /api/mirror/events
 * - Three privacy tiers: off / standard / deep
 * - Buffers events in chrome.storage.local and flushes every 30s
 */

import type { BehaviorEvent } from "../shared/types.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface BackendEndpoint {
  host: string;
  port: number;
}

interface MirrorEvent {
  event_type: string;
  url: string;
  title: string;
  context: string;
  duration_seconds: number;
  metadata: Record<string, unknown>;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Storage keys
// ---------------------------------------------------------------------------
const PRIVACY_TIER_KEY = "selfmirror_privacy_tier";
const EVENT_BUFFER_KEY = "selfmirror_event_buffer";
const BACKEND_ENDPOINT_KEY = "selfmirror_backend_endpoint";

const DEFAULT_PORT = 8421;
const DEFAULT_HOST = "127.0.0.1";

const TIER_OFF = "off";
const TIER_STANDARD = "standard";
const TIER_DEEP = "deep";

// ---------------------------------------------------------------------------
// Backend URL helper
// ---------------------------------------------------------------------------
async function getBackendUrl(path: string): Promise<string> {
  const stored = await chrome.storage.local.get<Record<string, unknown>>(BACKEND_ENDPOINT_KEY);
  const raw = stored[BACKEND_ENDPOINT_KEY] as BackendEndpoint | undefined;
  const ep: BackendEndpoint =
    raw && typeof raw === "object" && "host" in raw && "port" in raw
      ? raw
      : { host: DEFAULT_HOST, port: DEFAULT_PORT };
  return `http://${ep.host}:${ep.port}/api${path}`;
}

// ---------------------------------------------------------------------------
// Privacy tier
// ---------------------------------------------------------------------------
async function getPrivacyTier(): Promise<string> {
  const stored = await chrome.storage.local.get<Record<string, unknown>>(PRIVACY_TIER_KEY);
  const val = stored[PRIVACY_TIER_KEY];
  return typeof val === "string" ? val : TIER_STANDARD;
}

async function setPrivacyTier(tier: string): Promise<void> {
  await chrome.storage.local.set({ [PRIVACY_TIER_KEY]: tier });
  const tabs = await chrome.tabs.query({});
  for (const tab of tabs) {
    if (tab.id && !tab.url?.startsWith("chrome")) {
      chrome.tabs.sendMessage(tab.id, { action: "TIER_CHANGED", tier }).catch(() => {
        /* tab may not have content script */
      });
    }
  }
}

// ---------------------------------------------------------------------------
// Event buffer
// ---------------------------------------------------------------------------
async function getBuffer(): Promise<MirrorEvent[]> {
  const stored = await chrome.storage.local.get<Record<string, unknown>>(EVENT_BUFFER_KEY);
  const val = stored[EVENT_BUFFER_KEY];
  return (Array.isArray(val) ? val : []) as MirrorEvent[];
}

async function setBuffer(buffer: MirrorEvent[]): Promise<void> {
  const trimmed = buffer.slice(-50);
  await chrome.storage.local.set({ [EVENT_BUFFER_KEY]: trimmed });
}

async function addToBuffer(event: MirrorEvent): Promise<void> {
  const buffer = await getBuffer();
  buffer.push(event);
  await setBuffer(buffer);
}

// ---------------------------------------------------------------------------
// Tab tracking for DEEP tier
// ---------------------------------------------------------------------------
const tabLastSeen = {};

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (!changeInfo.url && !changeInfo.title) return;
  const tier = await getPrivacyTier();
  if (tier === TIER_OFF) return;

  const url = tab.url || "";
  const title = tab.title || "";

  // Skip chrome:// and extension:// pages
  if (url.startsWith("chrome") || url.startsWith("moz") || url.startsWith("about:")) return;

  const event = {
    event_type: "view",
    url,
    title,
    context: `訪問: ${title}`,
    duration_seconds: 0,
    metadata: {
      source_platform: "web",
      tab_id: String(tabId),
    },
    timestamp: Date.now(),
  };

  await addToBuffer(event);
  void flushIfNeeded();
});

// Track active tab for DEEP tier (window focus)
let lastActiveTabId: number | null = null;
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  lastActiveTabId = activeInfo.tabId;
  const tier = await getPrivacyTier();
  if (tier !== TIER_DEEP) return;

  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab.url && !tab.url.startsWith("chrome") && !tab.url.startsWith("moz")) {
      const buffer = await getBuffer();
      buffer.push({
        event_type: "active_window",
        url: tab.url || "",
        title: tab.title || "",
        context: `活躍視窗: ${tab.title}`,
        duration_seconds: 0,
        metadata: {
          source_platform: "web",
          tier: TIER_DEEP,
        },
        timestamp: Date.now(),
      });
      await setBuffer(buffer);
      void flushIfNeeded();
    }
  } catch {
    /* tab may be inaccessible */
  }
});

// ---------------------------------------------------------------------------
// Flush logic
// ---------------------------------------------------------------------------
async function flushIfNeeded() {
  const buffer = await getBuffer();
  if (buffer.length === 0) return;

  const tier = await getPrivacyTier();
  if (tier === TIER_OFF) return;

  // Flush every 5 events or every 30 seconds
  if (buffer.length >= 5) {
    void flushEvents();
  }
}

// Alarm-based flush every 30s
chrome.alarms.create("selfmirror-flush", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "selfmirror-flush") {
    void flushEvents();
  }
});

async function flushEvents() {
  const tier = await getPrivacyTier();
  if (tier === TIER_OFF) return;

  const events = await getBuffer();
  if (events.length === 0) return;

  // Take ownership of this batch
  await chrome.storage.local.set({ [EVENT_BUFFER_KEY]: [] });

  try {
    const url = await getBackendUrl("/mirror/events");
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tier, events }),
    });
    if (!response.ok) {
      // Put events back on failure
      const current = await getBuffer();
      await setBuffer([...events, ...current]);
    }
  } catch (err: unknown) {
    // Network error — put events back
    const current = await getBuffer();
    await setBuffer([...events, ...current]);
  }
}

// ---------------------------------------------------------------------------
// Message handler (for popup <-> service worker communication)
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "GET_PRIVACY_TIER") {
    getPrivacyTier().then((tier) => sendResponse({ tier }));
    return true;
  }
  if (message.action === "SET_PRIVACY_TIER") {
    setPrivacyTier(message.tier).then(() => sendResponse({ ok: true }));
    return true;
  }
  if (message.action === "GET_BACKEND_STATUS") {
    getBackendUrl("/mirror/privacy-status")
      .then((url) => fetch(url, { method: "GET" }).then((r) => ({ ok: r.ok, status: r.status })))
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  if (message.action === "PING_BACKEND") {
    getBackendUrl("/ping")
      .then((url) => fetch(url).then((r) => ({ ok: r.ok, status: r.status })))
      .then((result) => sendResponse(result))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  if (message.action === "FLUSH_NOW") {
    flushEvents().then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});

// Initial flush on startup
chrome.runtime.onStartup.addListener(() => {
  void flushEvents();
});
