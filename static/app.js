/* ReadLater — frontend */

const API = "/api/bookmarks";

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  q: "",
  type: "",
  read: "",
  tag: "",
};
let searchDebounce = null;

// ── DOM refs ──────────────────────────────────────────────────────────────
const addForm     = document.getElementById("add-form");
const urlInput    = document.getElementById("url-input");
const tagsInput   = document.getElementById("tags-input");
const addBtn      = document.getElementById("add-btn");
const addError    = document.getElementById("add-error");
const searchInput = document.getElementById("search-input");
const listEl      = document.getElementById("bookmark-list");
const emptyEl     = document.getElementById("empty-state");
const loadingEl   = document.getElementById("loading");
const tagCloud    = document.getElementById("tag-cloud");

// ── Init ──────────────────────────────────────────────────────────────────
(async function init() {
  await Promise.all([loadBookmarks(), loadTagCloud()]);
  bindFilters();
})();

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
    await Promise.all([loadBookmarks(), loadTagCloud()]);
  } finally {
    addBtn.disabled = false;
    addBtn.textContent = "Save";
  }
});

// ── Filters ───────────────────────────────────────────────────────────────
function bindFilters() {
  // Type chips
  document.querySelectorAll(".chip[data-type]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip[data-type]").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.type = chip.dataset.type;
      loadBookmarks();
    });
  });

  // Read chips
  document.querySelectorAll(".chip[data-read]").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip[data-read]").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.read = chip.dataset.read;
      loadBookmarks();
    });
  });

  // Search
  searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.q = searchInput.value.trim();
      loadBookmarks();
    }, 300);
  });
}

// ── Load bookmarks ────────────────────────────────────────────────────────
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
function renderCard(item) {
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
      // Filter by this tag
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

  const readBtn = document.createElement("button");
  readBtn.className = "btn-icon";
  readBtn.title = item.read ? "Mark unread" : "Mark read";
  readBtn.textContent = item.read ? "✓" : "○";
  readBtn.addEventListener("click", () => toggleRead(item, card, readBtn));
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
    await loadTagCloud();
    if (listEl.childElementCount === 0) emptyEl.classList.remove("hidden");
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
