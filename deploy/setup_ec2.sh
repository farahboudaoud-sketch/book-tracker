#!/usr/bin/env bash
# À exécuter SUR l'instance EC2 (Ubuntu 22.04/24.04), après connexion SSH.
# Usage : bash setup_ec2.sh <url_git_du_repo>
set -euo pipefail

REPO_URL="${1:?Usage: bash setup_ec2.sh <url_git_du_repo>}"
APP_DIR="/home/ubuntu/book-tracker"

echo "== Mise à jour du système =="
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git nginx

echo "== Récupération du code =="
if [ -d "$APP_DIR" ]; then
  cd "$APP_DIR" && git pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi

echo "== Environnement virtuel Python =="
cd "$APP_DIR/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "!! Pensez à créer backend/.env avec votre DATABASE_URL Neon avant de démarrer le service."
  cp .env.example .env
fi

echo "== Service systemd =="
sudo cp "$APP_DIR/deploy/booktracker.service" /etc/systemd/system/booktracker.service
sudo systemctl daemon-reload
sudo systemctl enable booktracker
sudo systemctl restart booktracker

echo "== Configuration Nginx (reverse proxy port 80 -> 8000) =="
sudo cp "$APP_DIR/deploy/nginx_booktracker.conf" /etc/nginx/sites-available/booktracker
sudo ln -sf /etc/nginx/sites-available/booktracker /etc/nginx/sites-enabled/booktracker
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "== Terminé. Le site est accessible sur http://<IP_publique_EC2>/ =="
