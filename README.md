# Carnet de lecture — suivi + recommandations

Application web pour :
- enregistrer les livres lus / en cours / à lire, avec suivi de la progression (pages lues) et note
- recommander de nouveaux livres à partir des auteurs et catégories des livres déjà lus

Stack : **FastAPI** (backend) + **PostgreSQL sur Neon** (base de données) + **HTML/CSS/JS vanilla** (frontend, servi par le backend) + **Google Books API** (recherche et métadonnées).

---

## 1. Mettre en place Neon (5 minutes)

1. Créer un compte sur [neon.tech](https://neon.tech) (gratuit pour un petit projet).
2. Créer un projet → une base `neondb` est créée par défaut.
3. Dans le dashboard Neon, aller dans **Connection Details** et copier la *connection string* — elle ressemble à :
   ```
   postgresql://<user>:<password>@ep-xxx-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Garder cette URL de côté : c'est la valeur de `DATABASE_URL`.

Les tables sont créées automatiquement au premier lancement de l'API (`Base.metadata.create_all` dans `main.py`) : aucune migration manuelle n'est nécessaire pour ce projet.

## 2. Tester en local avant de déployer

```bash
cd backend
conda env create -f environment.yml
conda activate book-tracker
cp .env.example .env      # puis coller votre DATABASE_URL Neon dedans
export $(cat .env | xargs)
uvicorn main:app --reload
```

Si l'environnement existe déjà et que vous modifiez `environment.yml`, mettez-le à jour avec :
```bash
conda env update -f environment.yml --prune
```

Ouvrir `http://localhost:8000` : le frontend est servi directement par FastAPI.

## 3. Déployer sur EC2

1. **Lancer une instance EC2** (Ubuntu 24.04, t2.micro/t3.micro suffit largement).
   - Security group : ouvrir le port **22** (SSH, votre IP) et le port **80** (HTTP, 0.0.0.0/0).
2. **Pousser le code sur un dépôt Git** (GitHub par ex.) — ou copier les fichiers via `scp` si vous ne voulez pas de repo public.
3. **Se connecter en SSH** :
   ```bash
   ssh -i votre_cle.pem ubuntu@<IP_publique_EC2>
   ```
4. **Lancer le script d'installation** :
   ```bash
   curl -O https://raw.githubusercontent.com/<vous>/<repo>/main/deploy/setup_ec2.sh
   bash setup_ec2.sh https://github.com/<vous>/<repo>.git
   ```
   Ce script installe Python/Nginx, clone le repo, crée le venv, installe les dépendances, configure le service systemd `booktracker` et le reverse proxy Nginx.
5. **Renseigner la variable d'environnement** : éditer `/home/ubuntu/book-tracker/backend/.env` avec votre vraie `DATABASE_URL` Neon, puis :
   ```bash
   sudo systemctl restart booktracker
   ```
6. Le site est accessible sur `http://<IP_publique_EC2>/`.

Pour un nom de domaine + HTTPS, ajouter Certbot (`sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx`) une fois un DNS pointé vers l'IP.

## 4. Planning indicatif (3-4 jours)

- **Jour 1** : Neon + backend en local (recherche Google Books, ajout à la bibliothèque, mise à jour de la progression). Tester avec l'interface Swagger (`/docs`).
- **Jour 2** : Frontend (bibliothèque, recherche, mise à jour de statut/progression/note).
- **Jour 3** : Recommandations (`recommend.py`) + tests avec un vrai historique de lecture.
- **Jour 4** : Déploiement EC2, ajustements CORS/Nginx, éventuellement HTTPS.

## 5. Pistes d'amélioration (après la V1)

- Authentification multi-utilisateur (actuellement mono-utilisateur, pas de login).
- Basculer sur Open Library si vous préférez ne pas dépendre d'une clé Google (`https://openlibrary.org/search.json?q=...`), le code de `google_books.py` est isolé pour faciliter le remplacement.
- Recommandations plus fines avec des embeddings de texte (ex. `sentence-transformers` sur les descriptions) plutôt que le matching auteur/catégorie actuel.
- Ajouter des tests (pytest) sur les routes FastAPI.

## Arborescence

```
book-tracker/
├── backend/
│   ├── main.py          # routes FastAPI
│   ├── models.py        # tables SQLAlchemy (Book, UserBook)
│   ├── schemas.py        # schémas Pydantic
│   ├── database.py       # connexion Neon
│   ├── google_books.py   # client API Google Books
│   ├── recommend.py       # logique de recommandation
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── deploy/
│   ├── setup_ec2.sh
│   ├── booktracker.service
│   └── nginx_booktracker.conf
└── README.md
```
