# Book Tracker — suivi de lecture + recommandations personnalisées

Application web pour :
- gérer sa bibliothèque personnelle : rechercher des livres, les ajouter, suivre leur statut (à lire / en cours / terminé), leur progression et leur note ;
- obtenir des recommandations personnalisées, calculées à partir d'une approche **hybride** combinant les auteurs/catégories des livres déjà appréciés **et** la proximité sémantique de leurs résumés, via des embeddings de texte.

Stack : **FastAPI** (backend) + **PostgreSQL sur Neon** (bibliothèque utilisateur, via SQLAlchemy) + **Neo4j AuraDB** (pool de livres + moteur de recommandation par recherche vectorielle) + **Sentence Transformers** (`BAAI/bge-m3`, génération des embeddings) + **HTML/CSS/JS vanilla** (frontend, servi par le backend) + **Google Books API** (recherche et métadonnées) + **Docker** (conteneurisation, déploiement sur Google Cloud Run).

---

## Comment fonctionne la recommandation

1. **Pool de livres** : `populate_graph.py` interroge Google Books sur une quarantaine de catégories, récupère ~2000 livres et les ingère dans Neo4j sous forme de nœuds `Book`, reliés à des nœuds `Author` et `Category`, chacun avec l'embedding de son résumé (index vectoriel Neo4j, similarité cosinus).
2. **Profil utilisateur** : à chaque appel de `/api/recommendations`, `recommend.py` construit le profil de goûts de l'utilisateur comme la moyenne pondérée (par la note) des embeddings des livres déjà lus, puis normalise ce vecteur.
3. **Recommandation** : ce profil est comparé aux livres du pool Neo4j via `CALL db.index.vector.queryNodes(...)`, en combinant cette similarité sémantique avec un score auteurs/catégories basé sur l'historique de lecture.

`embeddings.py` centralise le chargement du modèle (`BAAI/bge-m3`, choisi pour ses meilleures performances en français sur le MTEB et son contexte de 8192 tokens) et l'encodage des textes, réutilisé à la fois par l'ingestion (`populate_graph.py`) et la recommandation (`recommend.py`).

---

## 1. Mettre en place Neon — bibliothèque utilisateur (5 minutes)

1. Créer un compte sur [neon.tech](https://neon.tech) (gratuit pour un petit projet).
2. Créer un projet → une base `neondb` est créée par défaut.
3. Dans le dashboard Neon, aller dans **Connection Details** et copier la *connection string* — elle ressemble à :
   ```
   postgresql://<user>:<password>@ep-xxx-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Garder cette URL de côté : c'est la valeur de `DATABASE_URL`.

Les tables (`Book`, `UserBook`) sont créées automatiquement au premier lancement de l'API (`Base.metadata.create_all` dans `main.py`) : aucune migration manuelle n'est nécessaire pour ce projet.

## 2. Mettre en place Neo4j AuraDB — pool de livres + recommandations (5 minutes)

1. Créer une instance **AuraDB Free** sur [console.neo4j.io](https://console.neo4j.io).
2. À la création, Neo4j affiche une seule fois les identifiants : les récupérer immédiatement.
   - `NEO4J_URI` — de la forme `neo4j+s://xxxxxxxx.databases.neo4j.io`
   - `NEO4J_USER` — `neo4j` par défaut
   - `NEO4J_PASSWORD`
3. Renseigner ces trois variables dans `backend/.env` (voir `.env.example`).
4. Peupler le graphe une première fois (opération longue — plusieurs milliers d'appels à Google Books) :
   ```bash
   cd backend
   python populate_graph.py
   ```
   Ce script crée le schéma (index vectoriel `book_embeddings`, dimension 1024, similarité cosinus), puis ingère ~2000 livres avec leurs embeddings et leurs relations auteurs/catégories. À exécuter une seule fois — ou ponctuellement pour enrichir le pool, pas à chaque appel de l'API.

## 3. Tester en local avant de déployer

```bash
cd backend
conda env create -f environment.yml
conda activate book-tracker
cp .env.example .env      # coller DATABASE_URL (Neon), NEO4J_URI/USER/PASSWORD (Aura) et GOOGLE_BOOKS_API_KEY
export $(cat .env | xargs)
uvicorn main:app --reload
```

Si l'environnement existe déjà et que vous modifiez `environment.yml`, mettez-le à jour avec :
```bash
conda env update -f environment.yml --prune
```

Ouvrir `http://localhost:8000` : le frontend est servi directement par FastAPI.

Les principales routes de l'API :

| Route | Rôle |
|---|---|
| `GET /api/search` | recherche de livres via Google Books |
| `GET /book/{external_id}` | page de détail d'un livre |
| `POST /book/{external_id}/add` | ajout d'un livre à la bibliothèque depuis sa fiche |
| `GET /api/library` | contenu de la bibliothèque personnelle |
| `POST /api/library` | ajout manuel d'une entrée |
| `PATCH /api/library/{entry_id}` | mise à jour du statut / progression / note |
| `DELETE /api/library/{entry_id}` | suppression d'une entrée |
| `GET /api/recommendations` | recommandations personnalisées (Neo4j + embeddings) |

Toutes ces routes sont aussi explorables via l'interface Swagger générée automatiquement par FastAPI (`/docs`).

## 4. Déployer avec Docker sur Google Cloud Run

Le projet est conteneurisé (voir `Dockerfile` à la racine) : l'image installe les dépendances de `backend/requirements.txt`, copie le code, puis lance `uvicorn` sur le port fourni par la variable `PORT` — exactement le contrat attendu par Cloud Run.

1. **Construire et pousser l'image** (depuis la racine du projet, avec `gcloud` configuré sur votre projet GCP) :
   ```bash
   gcloud builds submit --tag gcr.io/<votre-projet-gcp>/book-tracker
   ```
2. **Déployer sur Cloud Run** :
   ```bash
   gcloud run deploy book-tracker \
     --image gcr.io/<votre-projet-gcp>/book-tracker \
     --platform managed \
     --region europe-west1 \
     --allow-unauthenticated \
     --set-env-vars DATABASE_URL="<votre DATABASE_URL Neon>",NEO4J_URI="<votre NEO4J_URI>",NEO4J_USER="neo4j",NEO4J_PASSWORD="<votre NEO4J_PASSWORD>",GOOGLE_BOOKS_API_KEY="<votre clé>"
   ```
   ⚠️ Ne jamais committer ces secrets dans le `Dockerfile` ou dans le dépôt — ils sont injectés à chaque déploiement via `--set-env-vars`, ou via **Secret Manager** pour un usage plus sérieux.
3. Cloud Run fournit automatiquement une URL HTTPS (`https://book-tracker-xxxxx-ew.a.run.app`) — pas de configuration Nginx/Certbot à gérer manuellement.

Pour tester l'image en local avant de la pousser :
```bash
docker build -t book-tracker .
docker run -p 8000:8000 -e PORT=8000 \
  -e DATABASE_URL="..." -e NEO4J_URI="..." -e NEO4J_USER="neo4j" -e NEO4J_PASSWORD="..." -e GOOGLE_BOOKS_API_KEY="..." \
  book-tracker
```

## 5. Google Books API — obtenir une clé

1. Ouvrir la [console Google Cloud](https://console.cloud.google.com).
2. Créer un nouveau projet (ou réutiliser celui du déploiement Cloud Run).
3. Rechercher **Books API** dans la bibliothèque d'API et l'activer.
4. Dans le menu **API et services → Identifiants**, créer une clé API, puis la restreindre à *Books API* uniquement.
5. Renseigner la clé dans `backend/.env` :
   ```
   GOOGLE_BOOKS_API_KEY=<votre clé>
   ```
   En local, relancer `uvicorn` après modification du `.env`. Sur Cloud Run, redéployer ou mettre à jour la variable d'environnement du service (`gcloud run services update book-tracker --set-env-vars GOOGLE_BOOKS_API_KEY=<votre clé>`), puis tester un appel de recherche pour valider.

## 6. Planning indicatif (4-5 jours)

- **Jour 1** : Neon + backend en local (recherche Google Books, ajout à la bibliothèque, mise à jour de la progression). Tester avec l'interface Swagger (`/docs`).
- **Jour 2** : Frontend (bibliothèque, recherche, mise à jour de statut/progression/note).
- **Jour 3** : Mise en place de Neo4j AuraDB, `populate_graph.py`, premier système de recommandation (score auteurs/catégories).
- **Jour 4** : Passage aux embeddings sémantiques (`embeddings.py`, `BAAI/bge-m3`) et système hybride dans `recommend.py`. Tests avec un vrai historique de lecture.
- **Jour 5** : Conteneurisation Docker, déploiement Cloud Run, ajustements des variables d'environnement.

## 7. Pistes d'amélioration (après la V1)

- Authentification multi-utilisateur (actuellement mono-utilisateur, pas de login).
- Basculer sur Open Library si vous préférez ne pas dépendre d'une clé Google (`https://openlibrary.org/search.json?q=...`), le code de `google_books.py` est isolé pour faciliter le remplacement.
- Construire plusieurs profils de goûts par utilisateur (plutôt qu'un seul vecteur moyen) pour mieux représenter des préférences très diverses, ou tester du clustering sur l'historique de lecture.
- Évaluer quantitativement la qualité des recommandations sur un jeu de données plus large, avec des métriques dédiées, pour comparer objectivement différentes pondérations du score hybride.
- Ajouter des tests (pytest) sur les routes FastAPI.

## Arborescence

```
book-tracker/
├── Dockerfile             # image de déploiement (Cloud Run)
├── requirements.txt
├── backend/
│   ├── main.py             # routes FastAPI
│   ├── models.py           # tables SQLAlchemy (Book, UserBook)
│   ├── schemas.py          # schémas Pydantic
│   ├── database.py         # connexion PostgreSQL (Neon)
│   ├── neo4j_client.py     # driver Neo4j partagé (AuraDB)
│   ├── embeddings.py       # wrapper Sentence Transformers (BAAI/bge-m3)
│   ├── google_books.py     # client API Google Books
│   ├── populate_graph.py   # ingestion du pool de livres dans Neo4j
│   ├── recommend.py        # logique de recommandation hybride
│   ├── requirements.txt
│   ├── environment.yml
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── README.md
```
