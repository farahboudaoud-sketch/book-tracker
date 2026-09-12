"""
Connexion partagée au driver Neo4j (instance AuraDB Free).
Un seul driver est créé par processus et réutilisé pour toutes les requêtes
(ouvrir une connexion par requête serait beaucoup trop lent).
"""
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

if not NEO4J_URI or not NEO4J_PASSWORD:
    raise RuntimeError(
        "NEO4J_URI et NEO4J_PASSWORD doivent être définis dans l'environnement "
        "(voir .env.example) — récupérables depuis la console Neo4j Aura."
    )

_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_driver():
    return _driver


def close_driver():
    _driver.close()
