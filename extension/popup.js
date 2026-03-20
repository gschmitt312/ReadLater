const DEFAULT_SERVER = "http://localhost:8000";

// ── DOM refs ──────────────────────────────────────────────────────────────
const viewSave      = document.getElementById("view-save");
const viewSettings  = document.getElementById("view-settings");
const urlPreview    = document.getElementById("url-preview");
const tagsInput     = document.getElementById("tags-input");
const saveBtn       = document.getElementById("save-btn");
const statusEl      = document.getElementById("status");
const openApp       = document.getElementById("open-app");
const settingsBtn   = document.getElementById("settings-btn");
const backBtn       = document.getElementById("back-btn");
const serverInput   = document.getElementById("server-input");
const saveSettingsBtn = document.getElementById("save-settings-btn");
const settingsStatus  = document.getElementById("settings-status");

let currentUrl = "";
let serverUrl  = DEFAULT_SERVER;

// ── Init ──────────────────────────────────────────────────────────────────
(async function init() {
  const stored = await chrome.storage.sync.get(["serverUrl"]);
  serverUrl = stored.serverUrl || DEFAULT_SERVER;
  serverInput.value = serverUrl;
  openApp.href = serverUrl;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentUrl = tab?.url || "";
  urlPreview.textContent = currentUrl;
})();

// ── Save ──────────────────────────────────────────────────────────────────
saveBtn.addEventListener("click", async () => {
  const tags = tagsInput.value.split(",").map(t => t.trim()).filter(Boolean);
  saveBtn.disabled = true;
  saveBtn.textContent = "Saving…";
  hideStatus();

  try {
    const res = await fetch(`${serverUrl}/api/bookmarks/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: currentUrl, tags }),
    });

    if (res.status === 409) {
      showStatus("Already saved!", "success");
    } else if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showStatus(err.detail || "Failed to save.", "error");
    } else {
      showStatus("Saved! ✓", "success");
      tagsInput.value = "";
      // Auto-close after success
      setTimeout(() => window.close(), 1200);
    }
  } catch {
    showStatus("Cannot reach server. Check Settings.", "error");
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "💾 Save to ReadLater";
  }
});

// ── Settings ──────────────────────────────────────────────────────────────
settingsBtn.addEventListener("click", () => {
  viewSave.classList.add("hidden");
  viewSettings.classList.remove("hidden");
});
backBtn.addEventListener("click", () => {
  viewSettings.classList.add("hidden");
  viewSave.classList.remove("hidden");
});
saveSettingsBtn.addEventListener("click", async () => {
  const url = serverInput.value.trim().replace(/\/$/, "");
  if (!url) return;
  await chrome.storage.sync.set({ serverUrl: url });
  serverUrl = url;
  openApp.href = url;
  showSettingsStatus("Saved!", "success");
});

// ── Helpers ───────────────────────────────────────────────────────────────
function showStatus(msg, type) {
  statusEl.textContent = msg;
  statusEl.className = `status ${type}`;
}
function hideStatus() {
  statusEl.className = "status hidden";
}
function showSettingsStatus(msg, type) {
  settingsStatus.textContent = msg;
  settingsStatus.className = `status ${type}`;
  setTimeout(() => { settingsStatus.className = "status hidden"; }, 2000);
}
