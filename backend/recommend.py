"""
Recommandation "content-based" très simple, sans dépendance ML lourde :
1. On regarde les livres marqués "read", en priorisant ceux bien notés.
2. On en extrait les auteurs et catégories les plus fréquents.
3. On interroge Google Books sur ces auteurs/catégories.
4. On retire les livres déjà présents dans la bibliothèque, on déduplique
   les différentes éditions d'une même œuvre (en ne gardant que la plus
   récente), puis on classe le tout par nombre de critères correspondants
   (auteur + catégorie).

C'est volontairement simple pour tenir en quelques jours de dev ; on peut
le remplacer plus tard par des embeddings (ex. sentence-transformers) sans
changer l'API exposée au frontend.
"""
import re
import unicodedata
from collections import Counter
from sqlalchemy.orm import Session
from models import Book, UserBook
from google_books import search_books


def _top_terms(counter: Counter, n: int) -> list[str]:
    return [term for term, _ in counter.most_common(n) if term]


def _normalize_title(title: str) -> str:
    """Normalise un titre pour repérer les rééditions d'une même œuvre
    (casse, ponctuation, ligatures œ/æ, accents, espaces multiples,
    sous-titre après ':' ignoré)."""
    title = title.split(":")[0]  # ignore souvent le sous-titre ("Titre: édition collector"...)
    title = title.lower()

    # Ligatures françaises -> forme décomposée (coeur == cœur)
    title = title.replace("œ", "oe").replace("æ", "ae")

    # Accents -> lettres de base (retire les diacritiques après décomposition Unicode)
    title = unicodedata.normalize("NFKD", title)
    title = "".join(ch for ch in title if not unicodedata.combining(ch))

    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _year_int(year) -> int:
    try:
        return int(year)
    except (TypeError, ValueError):
        return -1


def get_recommendations(db: Session, limit: int = 10) -> list[dict]:
    read_entries = (
        db.query(UserBook, Book)
        .join(Book, UserBook.book_id == Book.id)
        .filter(UserBook.status == "read")
        .all()
    )

    if not read_entries:
        return []

    author_counter, category_counter = Counter(), Counter()
    already_have_ids = set()

    for user_book, book in read_entries:
        already_have_ids.add(book.external_id)
        weight = user_book.rating or 3  # un livre bien noté pèse plus dans le profil
        for author in [a.strip() for a in book.authors.split(",") if a.strip()]:
            author_counter[author] += weight
        for category in [c.strip() for c in book.categories.split(",") if c.strip()]:
            category_counter[category] += weight

    # on inclut aussi les livres "to_read"/"reading" pour ne pas les re-suggérer
    all_entries = db.query(Book.external_id).all()
    already_have_ids.update(row[0] for row in all_entries)

    top_authors = _top_terms(author_counter, 6)
    top_categories = _top_terms(category_counter, 6)

    candidates: dict[str, dict] = {}
    scores: Counter = Counter()

    for author in top_authors:
        for result in search_books(f'inauthor:"{author}"', max_results=20):
            if result["external_id"] in already_have_ids:
                continue
            candidates[result["external_id"]] = result
            if author in result["authors"]:
                scores[result["external_id"]] += 2  # match auteur = signal fort

    for category in top_categories:
        for result in search_books(f'subject:"{category}"', max_results=20):
            if result["external_id"] in already_have_ids:
                continue
            candidates.setdefault(result["external_id"], result)
            scores[result["external_id"]] += 1

    # ------------------------------------------------------------------
    # Déduplication : une seule entrée par œuvre (titre normalisé),
    # on garde l'édition la plus récente et le meilleur score du groupe.
    # ------------------------------------------------------------------
    best_by_title: dict[str, dict] = {}
    best_score_by_title: dict[str, int] = {}

    for ext_id, candidate in candidates.items():
        norm_title = _normalize_title(candidate.get("title") or "")
        if not norm_title:
            norm_title = ext_id  # filet de sécurité si le titre est vide

        score = scores[ext_id]
        year = _year_int(candidate.get("published_year"))

        best_score_by_title[norm_title] = max(
            best_score_by_title.get(norm_title, 0), score
        )

        current_best = best_by_title.get(norm_title)
        if current_best is None or year > current_best["_year"]:
            enriched = dict(candidate)
            enriched["_year"] = year
            best_by_title[norm_title] = enriched

    ranked_titles = sorted(
        best_score_by_title.keys(),
        key=lambda t: best_score_by_title[t],
        reverse=True,
    )[:limit]

    return [
        {k: v for k, v in best_by_title[t].items() if k != "_year"}
        for t in ranked_titles
    ]