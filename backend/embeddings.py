"""
Wrapper partagé autour du modèle d'embeddings de phrases (sentence-transformers).
Chargé une seule fois par processus (paresseux), réutilisé à la fois par
populate_graph.py (ingestion des livres dans Neo4j) et recommend.py
(calcul du "profil de goûts" à comparer aux embeddings stockés dans Neo4j).

Modèle : BAAI/bge-m3 — meilleur que multilingual-e5-large sur le MTEB
français (58.79 vs 56.07), contexte 8192 tokens (les résumés de livres,
même longs, ne sont jamais tronqués), et pas de préfixe query:/passage:
à gérer contrairement aux modèles e5.
"""
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_DIM = 1024  # dimension des vecteurs produits par ce modèle

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]):
    """Encode une liste de textes en vecteurs normalisés (norme 1) :
    un simple produit scalaire entre deux vecteurs donne alors directement
    leur similarité cosinus."""
    return get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)