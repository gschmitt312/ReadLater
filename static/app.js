/* ReadLater — frontend */

const API = "/api/bookmarks";

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  view: "all",   // "all" | "queue"
  q: "",
  type: "",
  read: "",
  tag: "",
};
let searchDebounce = null;

// ── DOM refs ──────────────────────────────────────────────────────────────
const addForm      = document.getElementById("add-form");
const urlInput     = document.getElementById("url-input");
const tagsInput    = document.getElementById("tags-input");
const addBtn       = document.getElementById("add-btn");
const addError     = document.getElementById("add-error");
const searchInput  = document.getElementById("search-input");
const listEl       = document.getElementById("bookmark-list");
const emptyEl      = document.getElementById("empty-state");
const loadingEl    = document.getElementById("loading");
const tagCloud     = document.getElementById("tag-cloud");
const queueBadge   = document.getElementById("queue-badge");
// Queue
const viewAll      = document.getElementById("view-all");
const viewQueue    = document.getElementById("view-queue");
const queueNext    = document.getElementById("queue-next");
const queueNextCard= document.getElementById("queue-next-card");
const queueList    = document.getElementById("queue-list");
const queueEmpty   = document.getElementById("queue-empty");
const queueProgress= document.getElementById("queue-progress");
const progressFill = document.getElementById("progress-fill");
const progressLabel= document.getElementById("progress-label");
const markAllBtn   = document.getElementById("queue-mark-all");

// ── Init ──────────────────────────────────────────────────────────────────
(async function init() {
  await Promise.all([loadBookmarks(), loadTagCloud(), refreshQueueBadge()]);
  bindFilters();
  bindNavTabs();
})();

// ── Nav tabs ──────────────────────────────────────────────────────────────
function bindNavTabs() {
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      state.view = tab.dataset.view;
      if (state.view === "queue") {
        viewAll.classList.add("hidden");
        viewQueue.classList.remove("hidden");
        loadQueue();
      } else {
        viewQueue.classList.add("hidden");
        viewAll.classList.remove("hidden");
      }
    });
  });

  markAllBtn.addEventListener("click", markAllRead);
}

// ── Add bookmark ──────────────────────────────────────────────────────────
addForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url  = urlInput.value.trim();
  const tags = tagsInput.value.split(",").map(t => t.trim()).filter(Boolean);
  if (!url) return;

  addBtn.disabled = true;
  addBtn.textContent = "Saving…";
  hideError();

  try {
    const res = await fetch(API + "/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, tags }),
    });
    if (res.status === 409) {
      showError("This URL is already in your list.");
      return;
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showError(err.detail || "Failed to save bookmark.");
      return;
    }
    urlInput.value  = "";
    tagsInput.value = "";
    if (state.view === "queue") {
      await Promise.all([loadQueue(), refreshQueueBadge()]);
    } else {
      await Promise.all([loadBookmarks(), loadTagCloud(), refreshQueueBadge()]);
    }
  } finally {
    addBtn.disabled = false;
    addBtn.textContent = "Save";
  }
});

// ── Filters (All view) ────────────────────────────────────────────────────
function bindFilters() {
  document.querySelectorAll(".chip[data-type]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip[data-type]").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.type = chip.dataset.type;
      loadBookmarks();
    });
  });

  document.querySelectorAll(".chip[data-read]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip[data-read]").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.read = chip.dataset.read;
      loadBookmarks();
    });
  });

  searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.q = searchInput.value.trim();
      loadBookmarks();
    }, 300);
  });
}

// ── Load bookmarks (All view) ─────────────────────────────────────────────
async function loadBookmarks() {
  loadingEl.classList.remove("hidden");
  listEl.innerHTML = "";
  emptyEl.classList.add("hidden");

  const params = new URLSearchParams();
  if (state.q)    params.set("q",    state.q);
  if (state.type) params.set("type", state.type);
  if (state.read) params.set("read", state.read);
  if (state.tag)  params.set("tag",  state.tag);
  params.set("limit", "100");

  const res = await fetch(`${API}/?${params}`);
  loadingEl.classList.add("hidden");

  if (!res.ok) { listEl.innerHTML = `<p class="loading">Error loading bookmarks.</p>`; return; }
  const items = await res.json();

  if (items.length === 0) { emptyEl.classList.remove("hidden"); return; }
  items.forEach(item => listEl.appendChild(renderCard(item)));
}

// ── Queue view ────────────────────────────────────────────────────────────
async function loadQueue() {
  queueNext.classList.add("hidden");
  queueList.innerHTML = "";
  queueEmpty.classList.add("hidden");
  queueProgress.classList.add("hidden");

  // Fetch unread (queue order = oldest first) and total
  const [unreadRes, totalRes] = await Promise.all([
    fetch(`${API}/?read=false&limit=100`),
    fetch(`${API}/?limit=1`),
  ]);
  const unread = await unreadRes.json();

  // Count total for progress
  const totalItems = await fetchTotalCount();
  const readCount  = totalItems - unread.length;

  // Progress bar
  if (totalItems > 0) {
    queueProgress.classList.remove("hidden");
    const pct = Math.round((readCount / totalItems) * 100);
    progressFill.style.width = pct + "%";
    progressLabel.textContent = `${readCount} / ${totalItems} read`;
  }

  if (unread.length === 0) {
    queueEmpty.classList.remove("hidden");
    return;
  }

  // Sort oldest-first (they come newest-first from API)
  const sorted = [...unread].reverse();

  // "Up next" card
  const next = sorted[0];
  queueNextCard.innerHTML = "";
  const nextCard = renderCard(next, { queueMode: true });
  queueNextCard.appendChild(nextCard);
  queueNext.classList.remove("hidden");

  // Remaining list
  const remaining = sorted.slice(1);
  remaining.forEach(item => queueList.appendChild(renderCard(item)));
}

async function fetchTotalCount() {
  const res = await fetch(`${API}/?limit=200`);
  if (!res.ok) return 0;
  const items = await res.json();
  return items.length;
}

async function markAllRead() {
  const res = await fetch(`${API}/?read=false&limit=200`);
  const items = await res.json();
  await Promise.all(
    items.map(item =>
      fetch(`${API}/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ read: true }),
      })
    )
  );
  await Promise.all([loadQueue(), refreshQueueBadge()]);
}

// ── Queue badge ───────────────────────────────────────────────────────────
async function refreshQueueBadge() {
  const res = await fetch(`${API}/?read=false&limit=200`);
  if (!res.ok) return;
  const items = await res.json();
  const count = items.length;
  queueBadge.textContent = count;
  queueBadge.classList.toggle("hidden", count === 0);
}

// ── Tag cloud ─────────────────────────────────────────────────────────────
async function loadTagCloud() {
  const res = await fetch("/api/tags/");
  if (!res.ok) return;
  const tags = await res.json();
  tagCloud.innerHTML = "";
  if (tags.length === 0) { tagCloud.classList.add("hidden"); return; }
  tagCloud.classList.remove("hidden");

  tags.forEach(tag => {
    const btn = document.createElement("button");
    btn.className = "tag-btn" + (state.tag === tag ? " active" : "");
    btn.textContent = "#" + tag;
    btn.addEventListener("click", () => toggleTagFilter(tag, btn));
    tagCloud.appendChild(btn);
  });
}

function toggleTagFilter(tag, btn) {
  if (state.tag === tag) {
    state.tag = "";
    btn.classList.remove("active");
  } else {
    document.querySelectorAll(".tag-btn").forEach(b => b.classList.remove("active"));
    state.tag = tag;
    btn.classList.add("active");
  }
  loadBookmarks();
}

// ── Render a bookmark card ────────────────────────────────────────────────
function renderCard(item, opts = {}) {
  const { queueMode = false } = opts;

  const card = document.createElement("div");
  card.className = "card" + (item.read ? " is-read" : "");
  card.dataset.id = item.id;

  // Thumbnail
  let thumbEl;
  if (item.thumbnail) {
    thumbEl = document.createElement("img");
    thumbEl.className = "card-thumb";
    thumbEl.src = item.thumbnail;
    thumbEl.alt = "";
    thumbEl.onerror = () => { thumbEl.replaceWith(placeholderThumb(item.type)); };
  } else {
    thumbEl = placeholderThumb(item.type);
  }

  // Type badge
  const badge = document.createElement("span");
  badge.className = `type-badge type-${item.type}`;
  badge.textContent = item.type === "twitter" ? "𝕏 Post" : item.type === "youtube" ? "▶ YouTube" : "🌐 Web";

  // Title
  const title = document.createElement("a");
  title.className = "card-title";
  title.href = item.url;
  title.target = "_blank";
  title.rel = "noopener noreferrer";
  title.title = item.url;
  title.textContent = item.title || item.url;

  // Description
  const desc = document.createElement("p");
  desc.className = "card-desc";
  desc.textContent = item.description || "";

  // Footer: tags + date
  const footer = document.createElement("div");
  footer.className = "card-footer";

  item.tags.forEach(tag => {
    const t = document.createElement("span");
    t.className = "card-tag";
    t.textContent = "#" + tag;
    t.addEventListener("click", () => {
      if (state.view !== "all") return;
      document.querySelectorAll(".tag-btn").forEach(b => {
        b.classList.toggle("active", b.textContent === "#" + tag);
      });
      state.tag = tag;
      loadBookmarks();
    });
    footer.appendChild(t);
  });

  const date = document.createElement("span");
  date.className = "card-date";
  date.textContent = formatDate(item.created_at);
  footer.appendChild(date);

  // Card body
  const body = document.createElement("div");
  body.className = "card-body";
  const meta = document.createElement("div");
  meta.className = "card-meta";
  meta.appendChild(badge);
  body.appendChild(meta);
  body.appendChild(title);
  if (item.description) body.appendChild(desc);
  body.appendChild(footer);

  // Actions
  const actions = document.createElement("div");
  actions.className = "card-actions";

  if (queueMode) {
    // "Open & mark read" button for queue next-up card
    const openBtn = document.createElement("button");
    openBtn.className = "queue-open-btn";
    openBtn.textContent = "Open ↗";
    openBtn.addEventListener("click", async () => {
      window.open(item.url, "_blank", "noopener,noreferrer");
      await markRead(item);
      await Promise.all([loadQueue(), refreshQueueBadge()]);
    });
    actions.appendChild(openBtn);
  }

  const readBtn = document.createElement("button");
  readBtn.className = "btn-icon";
  readBtn.title = item.read ? "Mark unread" : "Mark read";
  readBtn.textContent = item.read ? "✓" : "○";
  readBtn.addEventListener("click", async () => {
    await toggleRead(item, card, readBtn);
    if (state.view === "queue") await Promise.all([loadQueue(), refreshQueueBadge()]);
    else await refreshQueueBadge();
  });
  actions.appendChild(readBtn);

  const delBtn = document.createElement("button");
  delBtn.className = "btn-icon btn-danger";
  delBtn.title = "Delete";
  delBtn.textContent = "✕";
  delBtn.addEventListener("click", () => deleteBookmark(item.id, card));
  actions.appendChild(delBtn);

  card.appendChild(thumbEl);
  card.appendChild(body);
  card.appendChild(actions);
  return card;
}

function placeholderThumb(type) {
  const el = document.createElement("div");
  el.className = "card-thumb-placeholder";
  el.textContent = type === "youtube" ? "▶" : type === "twitter" ? "𝕏" : "🔖";
  return el;
}

// ── Actions ───────────────────────────────────────────────────────────────
async function markRead(item) {
  await fetch(`${API}/${item.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ read: true }),
  });
  item.read = true;
}

async function toggleRead(item, card, btn) {
  const newRead = !item.read;
  await fetch(`${API}/${item.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ read: newRead }),
  });
  item.read = newRead;
  card.classList.toggle("is-read", newRead);
  btn.textContent = newRead ? "✓" : "○";
  btn.title = newRead ? "Mark unread" : "Mark read";
}

async function deleteBookmark(id, card) {
  if (!confirm("Delete this bookmark?")) return;
  const res = await fetch(`${API}/${id}`, { method: "DELETE" });
  if (res.ok || res.status === 204) {
    card.remove();
    await Promise.all([loadTagCloud(), refreshQueueBadge()]);
    if (state.view === "queue") {
      await loadQueue();
    } else if (listEl.childElementCount === 0) {
      emptyEl.classList.remove("hidden");
    }
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function showError(msg) {
  addError.textContent = msg;
  addError.classList.remove("hidden");
}
function hideError() {
  addError.classList.add("hidden");
}

function formatDate(iso) {
  const d = new Date(iso + "Z");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
