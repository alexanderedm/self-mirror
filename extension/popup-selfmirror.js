/**
 * SelfMirror — Popup JavaScript
 * Handles: privacy tier, mirror chat, profile display, settings
 */

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 8400;
const ENDPOINT_KEY = "selfmirror_backend_endpoint";
const TIER_KEY = "selfmirror_privacy_tier";

// ---------------------------------------------------------------------------
// Backend URL helpers
// ---------------------------------------------------------------------------
async function getEndpoint() {
  const result = await chrome.storage.local.get(ENDPOINT_KEY);
  const ep = result[ENDPOINT_KEY] || { host: DEFAULT_HOST, port: DEFAULT_PORT };
  return ep;
}

async function apiUrl(path) {
  const ep = await getEndpoint();
  return `http://${ep.host}:${ep.port}/api${path}`;
}

async function saveEndpoint(host, port) {
  await chrome.storage.local.set({
    [ENDPOINT_KEY]: { host: host || DEFAULT_HOST, port: parseInt(port) || DEFAULT_PORT },
  });
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
let toastTimer = null;
function showToast(msg, duration = 2500) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, duration);
}

// ---------------------------------------------------------------------------
// Backend status
// ---------------------------------------------------------------------------
async function checkBackendStatus() {
  const dot = document.getElementById("backend-dot");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  try {
    const url = await apiUrl("/mirror/privacy-status");
    const resp = await fetch(url, { method: "GET", cache: "no-cache" });
    if (resp.ok) {
      dot.className = "backend-dot ok";
      statusDot.className = "dot ok";
      statusText.textContent = "後端已連接";
      return true;
    }
  } catch {}
  dot.className = "backend-dot err";
  statusDot.className = "dot";
  statusText.textContent = "後端未連接";
  return false;
}

// ---------------------------------------------------------------------------
// Privacy tier
// ---------------------------------------------------------------------------
async function getCurrentTier() {
  const result = await chrome.storage.local.get(TIER_KEY);
  return result[TIER_KEY] || "standard";
}

async function setTier(tier) {
  await chrome.storage.local.set({ [TIER_KEY]: tier });
  // Notify service worker
  try {
    await chrome.runtime.sendMessage({ action: "SET_PRIVACY_TIER", tier });
  } catch {}
  updateTierUI(tier);
  showToast(`隱私等級：${{ off: "🔵 安靜", standard: "🟡 標準", deep: "🔴 深度" }[tier] || tier}`);
}

function updateTierUI(tier) {
  const btns = [
    { id: "btn-off", cls: "tier-btn" + (tier === "off" ? " active-off" : "") },
    { id: "btn-standard", cls: "tier-btn" + (tier === "standard" ? " active-standard" : "") },
    { id: "btn-deep", cls: "tier-btn" + (tier === "deep" ? " active-deep" : "") },
  ];
  btns.forEach(({ id, cls }) => {
    document.getElementById(id).className = cls;
  });
}

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function switchTab(tab) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.getElementById(`tab-${tab}`).classList.add("active");
  ["chat", "profile", "settings"].forEach((t) => {
    document.getElementById(`panel-${t}`).hidden = t !== tab;
  });
  if (tab === "profile") loadProfile();
  if (tab === "settings") loadSettings();
}

function showSettings() {
  switchTab("settings");
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------
let chatHistory = [];

function onChatKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
}

async function sendChat() {
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";

  appendMsg("user", msg);
  const mode = document.getElementById("chat-mode").value;

  const sendBtn = document.getElementById("chat-send");
  sendBtn.disabled = true;

  try {
    const url = await apiUrl("/mirror/chat");
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, mode }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    appendMsg("mirror", data.reply || "（暫無回應）");
  } catch (err) {
    appendMsg("system", `錯誤：${err.message}`);
  } finally {
    sendBtn.disabled = false;
  }
}

function appendMsg(role, text) {
  const container = document.getElementById("chat-msgs");
  const div = document.createElement("div");
  div.className = `msg msg-${role}`;
  div.textContent = text;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------
async function loadProfile() {
  const portrait = document.getElementById("profile-portrait");
  const traits = document.getElementById("profile-traits");
  const values = document.getElementById("profile-values");
  const needs = document.getElementById("profile-needs");
  const updated = document.getElementById("profile-updated");
  const tierStatus = document.getElementById("profile-tier-status");

  portrait.textContent = "（載入中...）";
  traits.innerHTML = "";
  values.innerHTML = "";
  needs.innerHTML = "";

  try {
    const [profileUrl, tier] = await Promise.all([
      apiUrl("/mirror/profile"),
      getCurrentTier(),
    ]);

    const [profileResp, tierResp] = await Promise.all([
      fetch(profileUrl, { cache: "no-cache" }),
      apiUrl("/mirror/privacy-status").then((u) => fetch(u, { cache: "no-cache" })),
    ]);

    if (!profileResp.ok) throw new Error(`HTTP ${profileResp.status}`);
    const profile = await profileResp.json();

    portrait.textContent = profile.portrait || "（尚未建立畫像）";
    traits.innerHTML = (profile.core_traits || []).map((t) => `<span class="trait-chip">${t}</span>`).join("");
    values.innerHTML = (profile.values || []).map((v) => `<span class="value-chip">${v}</span>`).join("");
    needs.innerHTML = (profile.deep_needs || []).map((n) => `<span class="need-chip">${n}</span>`).join("");
    updated.textContent = profile.updated_at ? `更新於：${profile.updated_at}` : "";

    if (tierResp.ok) {
      const tierData = await tierResp.json();
      tierStatus.textContent = {
        off: "🔵 安靜 — 不收集任何數據", standard: "🟡 標準 — URL、標題、停留時間", deep: "🔴 深度 — + 活躍視窗標題"
      }[tierData.tier] || `目前：${tierData.tier}`;
    } else {
      tierStatus.textContent = "（無法讀取狀態）";
    }
  } catch (err) {
    portrait.textContent = `（載入失敗：${err.message}）`;
  }
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
async function loadSettings() {
  const ep = await getEndpoint();
  document.getElementById("backend-host").value = ep.host;
  document.getElementById("backend-port").value = ep.port;
  const tier = await getCurrentTier();
  updateTierUI(tier);
}

async function saveBackend() {
  const host = document.getElementById("backend-host").value.trim();
  const port = parseInt(document.getElementById("backend-port").value);
  if (!port || port < 1 || port > 65535) {
    showToast("請輸入有效的端口號（1-65535）");
    return;
  }
  await saveEndpoint(host, port);
  showToast("後端設置已保存");
  await checkBackendStatus();
}

async function flushEvents() {
  try {
    await chrome.runtime.sendMessage({ action: "FLUSH_NOW" });
    showToast("事件已強 制上報");
  } catch (err) {
    showToast(`失敗：${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function runInitScan() {
  showToast("正在掃描本地 AI 工具對話...");
  try {
    const url = await apiUrl("/mirror/init-scan");
    const resp = await fetch(url, { method: "POST", cache: "no-cache" });
    const data = await resp.json();
    showToast(`掃描完成：${data.sessions_found} 個對話，來源：${data.sources.join(", ")}`);
  } catch (err) {
    showToast(`掃描失敗：${err.message}`);
  }
}

async function runInitBuild() {
  showToast("正在生成初始畫像（需 LLM，可能需要幾十秒）...");
  try {
    const url = await apiUrl("/mirror/init-build");
    const resp = await fetch(url, { method: "POST", cache: "no-cache" });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    showToast("畫像生成完成！");
    if (data.portrait) {
      appendMsg("system", "✅ 初始畫像已建立，請切換到「畫像」標籤查看");
    }
  } catch (err) {
    showToast(`生成失敗：${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  // Load current tier
  const tier = await getCurrentTier();
  updateTierUI(tier);

  // Check backend
  await checkBackendStatus();
  setInterval(checkBackendStatus, 15000);

  // Add welcome message if chat is empty
  const msgs = document.getElementById("chat-msgs");
  if (msgs.children.length <= 1) {
    const tier = await getCurrentTier();
    if (tier === "off") {
      appendMsg("system", "🔵 目前處於「安靜」模式，聊天記錄不會影響畫像");
    }
  }
});
