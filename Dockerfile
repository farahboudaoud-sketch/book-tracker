FROM python:3.11

WORKDIR /home/app

# 1. Copier uniquement les dépendances
COPY backend/requirements.txt /dependencies/requirements.txt

# 2. Installer les dépendances
RUN pip install --no-cache-dir -r /dependencies/requirements.txt

# 3. Copier le code de l'application
COPY . .

# Variables d'environnement de l'application
# ⚠️ Ne pas mettre de secrets directement dans le Dockerfile
ENV DATABASE_URL=$DATABASE_URL
ENV GOOGLE_BOOKS_API_KEY=$GOOGLE_BOOKS_API_KEY
ENV PORT=$PORT

EXPOSE $PORT

CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"]