FROM python:3.11-slim

WORKDIR /home/app
COPY . .
# Variables d'environnement de l'application
# ⚠️ Ces valeurs sont gravées dans l'image : ne pas rendre l'image publique.
ENV DATABASE_URL=$DATABASE_URL
ENV GOOGLE_BOOKS_API_KEY=$GOOGLE_BOOKS_API_KEY

# Dépendances Python (chemin relatif au dossier backend/ du repo)
COPY backend/requirements.txt /dependencies/requirements.txt
RUN pip install --no-cache-dir -r /dependencies/requirements.txt

# Code de l'application (backend + frontend)


EXPOSE 8080

CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]