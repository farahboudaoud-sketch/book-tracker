"""
Recommandation "content-based" très simple, sans dépendance ML lourde :
1. On regarde les livres marqués "read", en priorisant ceux bien notés.
2. On en extrait les auteurs et catégories les plus fréquents.
3. On interroge Google Books sur ces auteurs/catégories.
4. On retire les livres déjà présents dans la bibliothèque et on classe
   les résultats par nombre de critères correspondants (auteur + catégorie).

C'est volontairement simple pour tenir en quelques jours de dev ; on peut
le remplacer plus tard par des embeddings (ex. sentence-transformers) sans
changer l'API exposée au frontend.
"""
from collections import Counter
from sqlalchemy.orm import Session
from models import Book, UserBook
from google_books import search_books


def _top_terms(counter: Counter, n: int) -> list[str]:
    return [term for term, _ in counter.most_common(n) if term]


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

    top_authors = _top_terms(author_counter, 3)
    top_categories = _top_terms(category_counter, 3)

    candidates: dict[str, dict] = {}
    scores: Counter = Counter()

    for author in top_authors:
        for result in search_books(f'inauthor:"{author}"', max_results=8):
            if result["external_id"] in already_have_ids:
                continue
            candidates[result["external_id"]] = result
            if author in result["authors"]:
                scores[result["external_id"]] += 2  # match auteur = signal fort

    for category in top_categories:
        for result in search_books(f'subject:"{category}"', max_results=8):
            if result["external_id"] in already_have_ids:
                continue
            candidates.setdefault(result["external_id"], result)
            scores[result["external_id"]] += 1

    ranked_ids = [ext_id for ext_id, _ in scores.most_common(limit)]
    return [candidates[ext_id] for ext_id in ranked_ids if ext_id in candidates]
