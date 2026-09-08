const API = ""; // même origine que le frontend (voir StaticFiles côté FastAPI)

const cardTemplate = document.getElementById("book-card-template");

// ---------- Navigation par onglets ----------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "library") loadLibrary();
    if (btn.dataset.tab === "recos") loadRecommendations();
  });
});

// ---------- Bibliothèque ----------
let currentStatusFilter = "";

document.querySelectorAll(".filter-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentStatusFilter = btn.dataset.status;
    loadLibrary();
  });
});

async function loadLibrary() {
  const url = currentStatusFilter
    ? `${API}/api/library?status=${currentStatusFilter}`
    : `${API}/api/library`;
  const entries = await fetch(url).then((r) => r.json());
  const grid = document.getElementById("library-grid");
  grid.innerHTML = "";
  document.getElementById("library-empty").hidden = entries.length > 0;

  for (const entry of entries) {
    grid.appendChild(renderLibraryCard(entry));
  }
}

function renderLibraryCard(entry) {
  const node = cardTemplate.content.cloneNode(true);
  const book = entry.book;

  node.querySelector("img").src = book.thumbnail || "";
  node.querySelector("img").alt = book.title;
  node.querySelector(".title").textContent = book.title;
  node.querySelector(".authors").textContent = book.authors || "Auteur inconnu";

  // Sélecteur de statut
  const statusRow = node.querySelector(".status-row");
  const select = document.createElement("select");
  [["to_read", "À lire"], ["reading", "En cours"], ["read", "Terminé"]].forEach(([val, label]) => {
    const opt = document.createElement("option");
    opt.value = val;
    opt.textContent = label;
    if (val === entry.status) opt.selected = true;
    select.appendChild(opt);
  });
  select.addEventListener("change", async () => {
    await updateEntry(entry.id, { status: select.value });
    loadLibrary();
  });
  statusRow.appendChild(select);

  // Barre de progression (uniquement si en cours et total_pages connu)
  if (entry.status === "reading" && entry.total_pages > 0) {
    const progressRow = node.querySelector(".progress-row");
    progressRow.hidden = false;
    const pct = Math.min(100, Math.round((entry.current_page / entry.total_pages) * 100));
    progressRow.querySelector(".progress-fill").style.width = `${pct}%`;
    progressRow.querySelector(".progress-label").textContent = `${entry.current_page}/${entry.total_pages} p.`;
    progressRow.addEventListener("click", async () => {
      const page = prompt("Page actuelle ?", entry.current_page);
      if (page === null) return;
      await updateEntry(entry.id, { current_page: parseInt(page, 10) || 0 });
      loadLibrary();
    });
  }

  // Étoiles de notation (uniquement si terminé)
  if (entry.status === "read") {
    const ratingRow = node.querySelector(".rating-row");
    ratingRow.hidden = false;
    for (let i = 1; i <= 5; i++) {
      const starBtn = document.createElement("button");
      starBtn.textContent = "★";
      if (entry.rating && i <= entry.rating) starBtn.classList.add("filled");
      starBtn.addEventListener("click", async () => {
        await updateEntry(entry.id, { rating: i });
        loadLibrary();
      });
      ratingRow.appendChild(starBtn);
    }
  }

  const actionBtn = node.querySelector(".action-btn");
  actionBtn.textContent = "Retirer";
  actionBtn.classList.add("remove");
  actionBtn.addEventListener("click", async () => {
    if (!confirm(`Retirer « ${book.title} » de votre bibliothèque ?`)) return;
    await fetch(`${API}/api/library/${entry.id}`, { method: "DELETE" });
    loadLibrary();
  });

  return node;
}

async function updateEntry(entryId, payload) {
  await fetch(`${API}/api/library/${entryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------- Recherche ----------
document.getElementById("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = document.getElementById("search-input").value.trim();
  if (!q) return;
  const results = await fetch(`${API}/api/search?q=${encodeURIComponent(q)}`).then((r) => r.json());
  renderResultGrid("search-grid", results);
});

function renderResultGrid(gridId, books) {
  const grid = document.getElementById(gridId);
  grid.innerHTML = "";
  for (const book of books) {
    const node = cardTemplate.content.cloneNode(true);
    node.querySelector("img").src = book.thumbnail || "";
    node.querySelector("img").alt = book.title;
    node.querySelector(".title").textContent = book.title;
    node.querySelector(".authors").textContent = book.authors || "Auteur inconnu";
    node.querySelector(".status-row").remove();

    const actionBtn = node.querySelector(".action-btn");
    actionBtn.textContent = "Ajouter à ma bibliothèque";
    actionBtn.addEventListener("click", async () => {
      const res = await fetch(`${API}/api/library`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          external_id: book.external_id,
          title: book.title,
          authors: book.authors,
          categories: book.categories,
          thumbnail: book.thumbnail,
          published_year: book.published_year,
          status: "to_read",
        }),
      });
      if (res.ok) {
        actionBtn.textContent = "Ajouté ✓";
        actionBtn.disabled = true;
      } else {
        const err = await res.json();
        alert(err.detail || "Erreur lors de l'ajout");
      }
    });
    grid.appendChild(node);
  }
}

// ---------- Recommandations ----------
async function loadRecommendations() {
  const results = await fetch(`${API}/api/recommendations`).then((r) => r.json());
  document.getElementById("reco-empty").hidden = results.length > 0;
  renderResultGrid("reco-grid", results);
}

// Chargement initial
loadLibrary();
