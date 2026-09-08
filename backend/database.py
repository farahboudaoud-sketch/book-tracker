import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# L'URL Neon ressemble à :
# postgresql://user:password@ep-xxx-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "La variable d'environnement DATABASE_URL n'est pas définie. "
        "Copiez .env.example vers .env et renseignez l'URL de connexion Neon."
    )

# Neon coupe les connexions inactives : pool_pre_ping évite les erreurs "connexion fermée"
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
