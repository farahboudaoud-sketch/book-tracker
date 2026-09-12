"""
Recommandations basées sur un pool de ~2000 livres stocké dans un graphe
Neo4j (AuraDB Free), combinant deux signaux en une seule requête Cypher :

1. Similarité vectorielle : l'index vectoriel natif de Neo4j compare
   l'embedding de chaque livre du pool à ton "profil de goûts" (moyenne
   pondérée par la note des embeddings des résumés de tes livres "read").
2. Recouvrement de graphe : nombre d'auteurs/catégories partagés entre
   tes livres déjà lus et chaque candidat, via les relations
   (:Book)-[:BY]->(:Author) et (:Book)-[:IN_CATEGORY]->(:Category).

La bibliothèque personnelle (statuts, notes, progression) reste dans Neon :
seul le pool de candidats et leurs embeddings vivent dans Neo4j. Aucun appel
à l'API Google Books n'est plus fait ici — tout se joue sur le pool déjà
ingéré par populate_graph.py.
"""
import re
import unicodedata
import difflib

import numpy as np
from sqlalchemy.orm import Session

from models import Book, UserBook
from embeddings import embed_texts
from neo4j_client import get_driver

SIMILARITY_WEIGHT = 5
AUTHOR_WEIGHT = 2
CATEGORY_WEIGHT = 1


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("œ", "oe").replace("æ", "ae")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_title(title: str) -> str:
    title = title.split(":")[0]
    return _normalize_text(title)


def _primary_author(authors: str) -> str:
    first = authors.split(",")[0] if authors else ""
    return _normalize_text(first)


def _titles_overlap(title_a: str, title_b: str) -> bool:
    if not title_a or not title_b:
        return False
    if title_a in title_b or title_b in title_a:
        return True
    return difflib.SequenceMatcher(None, title_a, title_b).ratio() >= 0.6


def _build_user_profile(read_entries) -> list[float] | None:
    """Moyenne pondérée (par note) des embeddings des résumés des livres
    déjà lus. None si aucun résumé disponible."""
    texts, weights = [], []
    for user_book, book in read_entries:
        if book.description:
            texts.append(book.description)
            weights.append(user_book.rating or 3)

    if not texts:
        return None

    vectors = embed_texts(texts)
    weights = np.array(weights, dtype=float)
    profile = np.average(vectors, axis=0, weights=weights)
    norm = np.linalg.norm(profile)
    return (profile / norm).tolist() if norm > 0 else None


def get_recommendations(db: Session, limit: int = 10) -> list[dict]:
    read_entries = (
        db.query(UserBook, Book)
        .join(Book, UserBook.book_id == Book.id)
        .filter(UserBook.status == "read")
        .all()
    )

    if not read_entries:
        return []

    profile = _build_user_profile(read_entries)
    if profile is None:
        return []  # aucun résumé exploitable parmi les livres lus

    read_external_ids = [book.external_id for _, book in read_entries]
    already_have_ids = [row[0] for row in db.query(Book.external_id).all()]

    fetch_limit = max(limit * 5, 50)  # marge pour compenser dédup + exclusions

    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (read:Book) WHERE read.external_id IN $read_ids
            WITH collect(read) AS readBooks

            CALL db.index.vector.queryNodes('book_embeddings', $k, $profile_vector)
            YIELD node AS candidate, score AS similarity
            WHERE NOT candidate.external_id IN $exclude_ids

            OPTIONAL MATCH (candidate)-[:BY]->(a:Author)<-[:BY]-(rb:Book)
            WHERE rb IN readBooks
            WITH candidate, similarity, readBooks, count(DISTINCT a) AS authorOverlap

            OPTIONAL MATCH (candidate)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(rb2:Book)
            WHERE rb2 IN readBooks
            WITH candidate, similarity, authorOverlap, count(DISTINCT c) AS categoryOverlap

            RETURN candidate.external_id AS external_id,
                   candidate.title AS title,
                   candidate.authors AS authors,
                   candidate.categories AS categories,
                   candidate.thumbnail AS thumbnail,
                   candidate.published_year AS published_year,
                   similarity, authorOverlap, categoryOverlap
            ORDER BY (authorOverlap * $author_weight
                      + categoryOverlap * $category_weight
                      + similarity * $similarity_weight) DESC
            LIMIT $fetch_limit
            """,
            read_ids=read_external_ids,
            profile_vector=profile,
            exclude_ids=already_have_ids,
            k=fetch_limit,
            fetch_limit=fetch_limit,
            author_weight=AUTHOR_WEIGHT,
            category_weight=CATEGORY_WEIGHT,
            similarity_weight=SIMILARITY_WEIGHT,
        )
        candidates = [dict(record) for record in result]

    # ------------------------------------------------------------------
    # Regroupement : un seul livre par (auteur + titre qui se recoupe),
    # comme avant — appliqué ici sur les résultats renvoyés par Neo4j.
    # ------------------------------------------------------------------
    groups: list[dict] = []

    for candidate in candidates:
        norm_title = _normalize_title(candidate.get("title") or "") or candidate["external_id"]
        author_key = _primary_author(candidate.get("authors") or "")
        final_score = (
            candidate["authorOverlap"] * AUTHOR_WEIGHT
            + candidate["categoryOverlap"] * CATEGORY_WEIGHT
            + candidate["similarity"] * SIMILARITY_WEIGHT
        )

        matched_group = None
        if author_key:
            for group in groups:
                if group["author"] == author_key and _titles_overlap(group["title"], norm_title):
                    matched_group = group
                    break

        if matched_group is None:
            groups.append({
                "author": author_key,
                "title": norm_title,
                "score": final_score,
                "data": candidate,
            })
        elif final_score > matched_group["score"]:
            matched_group["score"] = final_score
            matched_group["data"] = candidate
            matched_group["title"] = norm_title

    groups.sort(key=lambda g: g["score"], reverse=True)

    return [
        {
            "external_id": g["data"]["external_id"],
            "title": g["data"]["title"],
            "authors": g["data"]["authors"],
            "categories": g["data"]["categories"],
            "thumbnail": g["data"]["thumbnail"],
            "published_year": g["data"]["published_year"],
        }
        for g in groups[:limit]
    ]