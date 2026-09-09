const API = "";

const cardTemplate = document.getElementById("book-card-template");


// ======================================================
// NAVIGATION PAR ONGLETS
// ======================================================

document.querySelectorAll(".tab-btn").forEach((btn) => {

  btn.addEventListener("click", () => {

    document
      .querySelectorAll(".tab-btn")
      .forEach((b) => b.classList.remove("active"));

    document
      .querySelectorAll(".tab-panel")
      .forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");

    document
      .getElementById(`tab-${btn.dataset.tab}`)
      .classList.add("active");

    if (btn.dataset.tab === "library") {
      loadLibrary();
    }

    if (btn.dataset.tab === "recos") {
      loadRecommendations();
    }

  });

});


// ======================================================
// BIBLIOTHÈQUE
// ======================================================

let currentStatusFilter = "";

document.querySelectorAll(".filter-btn").forEach((btn) => {

  btn.addEventListener("click", () => {

    document
      .querySelectorAll(".filter-btn")
      .forEach((b) => b.classList.remove("active"));

    btn.classList.add("active");

    currentStatusFilter = btn.dataset.status;

    loadLibrary();

  });

});


async function loadLibrary() {

  const url = currentStatusFilter
    ? `${API}/api/library?status=${currentStatusFilter}`
    : `${API}/api/library`;

  const response = await fetch(url);

  const entries = await response.json();

  const grid = document.getElementById("library-grid");

  grid.innerHTML = "";

  document.getElementById("library-empty").hidden =
    entries.length > 0;

  for (const entry of entries) {

    grid.appendChild(
      renderLibraryCard(entry)
    );

  }

}


// ======================================================
// LIEN VERS LA PAGE DE DÉTAIL (image + titre)
// ======================================================

function applyDetailLinks(node, book) {

  const coverLink = document.createElement("a");
  coverLink.href = `/book/${book.external_id}`;
  coverLink.className = "cover-link";

  const img = node.querySelector("img");
  img.src = book.thumbnail || "";
  img.alt = book.title;
  img.replaceWith(coverLink);
  coverLink.appendChild(img);

  const titleLink = document.createElement("a");
  titleLink.href = `/book/${book.external_id}`;
  titleLink.className = "title-link";
  titleLink.textContent = book.title;

  const titleEl = node.querySelector(".title");
  titleEl.textContent = "";
  titleEl.appendChild(titleLink);

}


// ======================================================
// CARTE D'UN LIVRE DE LA BIBLIOTHÈQUE
// ======================================================

function renderLibraryCard(entry) {

  const node =
    cardTemplate.content.cloneNode(true);

  const book = entry.book;


  applyDetailLinks(node, book);


  // Auteur
  node.querySelector(".authors").textContent =
    book.authors || "Auteur inconnu";


  // ----------------------------------------------------
  // STATUT
  // ----------------------------------------------------

  const statusRow =
    node.querySelector(".status-row");

  const select =
    document.createElement("select");

  [
    ["to_read", "À lire"],
    ["reading", "En cours"],
    ["read", "Terminé"]
  ].forEach(([value, label]) => {

    const option =
      document.createElement("option");

    option.value = value;

    option.textContent = label;

    if (value === entry.status) {
      option.selected = true;
    }

    select.appendChild(option);

  });


  select.addEventListener("change", async () => {

    await updateEntry(
      entry.id,
      {
        status: select.value
      }
    );

    loadLibrary();

  });


  statusRow.appendChild(select);


  // ----------------------------------------------------
  // PROGRESSION
  // ----------------------------------------------------

  if (
    entry.status === "reading" &&
    entry.total_pages > 0
  ) {

    const progressRow =
      node.querySelector(".progress-row");

    progressRow.hidden = false;

    const pct =
      Math.min(
        100,
        Math.round(
          (entry.current_page /
            entry.total_pages) *
          100
        )
      );

    progressRow
      .querySelector(".progress-fill")
      .style.width = `${pct}%`;

    progressRow
      .querySelector(".progress-label")
      .textContent =
      `${entry.current_page}/${entry.total_pages} p.`;


    progressRow.addEventListener(
      "click",
      async () => {

        const page =
          prompt(
            "Page actuelle ?",
            entry.current_page
          );

        if (page === null) {
          return;
        }

        await updateEntry(
          entry.id,
          {
            current_page:
              parseInt(page, 10) || 0
          }
        );

        loadLibrary();

      }
    );

  }


  // ----------------------------------------------------
  // NOTATION
  // ----------------------------------------------------

  if (entry.status === "read") {

    const ratingRow =
      node.querySelector(".rating-row");

    ratingRow.hidden = false;

    for (let i = 1; i <= 5; i++) {

      const starBtn =
        document.createElement("button");

      starBtn.textContent = "★";

      if (
        entry.rating &&
        i <= entry.rating
      ) {
        starBtn.classList.add("filled");
      }

      starBtn.addEventListener(
        "click",
        async () => {

          await updateEntry(
            entry.id,
            {
              rating: i
            }
          );

          loadLibrary();

        }
      );

      ratingRow.appendChild(starBtn);

    }

  }


  // ----------------------------------------------------
  // RETIRER
  // ----------------------------------------------------

  const actionBtn =
    node.querySelector(".action-btn");

  actionBtn.textContent =
    "Retirer";

  actionBtn.classList.add("remove");


  actionBtn.addEventListener(
    "click",
    async () => {

      if (
        !confirm(
          `Retirer « ${book.title} » de votre bibliothèque ?`
        )
      ) {
        return;
      }

      await fetch(
        `${API}/api/library/${entry.id}`,
        {
          method: "DELETE"
        }
      );

      loadLibrary();

    }
  );


  return node;

}


// ======================================================
// MODIFICATION D'UNE ENTRÉE
// ======================================================

async function updateEntry(
  entryId,
  payload
) {

  await fetch(
    `${API}/api/library/${entryId}`,
    {
      method: "PATCH",

      headers: {
        "Content-Type":
          "application/json"
      },

      body: JSON.stringify(payload)
    }
  );

}


// ======================================================
// RECHERCHE
// ======================================================

document
  .getElementById("search-form")
  .addEventListener(
    "submit",
    async (e) => {

      e.preventDefault();

      const q =
        document
          .getElementById("search-input")
          .value
          .trim();

      if (!q) {
        return;
      }

      const response =
        await fetch(
          `${API}/api/search?q=${encodeURIComponent(q)}`
        );

      const results =
        await response.json();

      renderResultGrid(
        "search-grid",
        results
      );

    }
  );


// ======================================================
// CARTES DES RECOMMANDATIONS / RECHERCHE
// ======================================================

function renderResultGrid(
  gridId,
  books
) {

  const grid =
    document.getElementById(gridId);

  grid.innerHTML = "";


  for (const book of books) {

    const node =
      cardTemplate.content.cloneNode(true);


    applyDetailLinks(node, book);


    // Auteur
    node.querySelector(".authors").textContent =
      book.authors || "Auteur inconnu";


    // Pas de statut sur les résultats
    node
      .querySelector(".status-row")
      .remove();


    // --------------------------------------------------
    // AJOUTER À LA BIBLIOTHÈQUE
    // --------------------------------------------------

    const actionBtn =
      node.querySelector(".action-btn");

    actionBtn.textContent =
      "Ajouter à ma bibliothèque";


    actionBtn.addEventListener(
      "click",
      async () => {

        const response =
          await fetch(
            `${API}/api/library`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json"
              },

              body: JSON.stringify({

                external_id:
                  book.external_id,

                title:
                  book.title,

                authors:
                  book.authors || "",

                categories:
                  book.categories || "",

                thumbnail:
                  book.thumbnail || null,

                published_year:
                  book.published_year || null,

                description:
                  book.description || null,

                status:
                  "to_read"

              })

            }
          );


        if (response.ok) {

          actionBtn.textContent =
            "Ajouté ✓";

          actionBtn.disabled =
            true;

        } else {

          let errorMessage =
            "Erreur lors de l'ajout";

          try {

            const error =
              await response.json();

            errorMessage =
              error.detail ||
              errorMessage;

          } catch (e) {
            // Rien à faire
          }

          alert(errorMessage);

        }

      }
    );


    grid.appendChild(node);

  }

}


// ======================================================
// RECOMMANDATIONS
// ======================================================

async function loadRecommendations() {

  const response =
    await fetch(
      `${API}/api/recommendations`
    );

  const results =
    await response.json();


  document.getElementById(
    "reco-empty"
  ).hidden =
    results.length > 0;


  renderResultGrid(
    "reco-grid",
    results
  );

}


// ======================================================
// CHARGEMENT INITIAL
// ======================================================

loadLibrary();
