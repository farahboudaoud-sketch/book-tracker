"""
Répare le graphe EXISTANT sans tout ré-ingérer.

Pour chaque noeud :Book déjà en base, on interroge l'endpoint de détail
/volumes/{id} de Google Books (le seul qui renvoie TOUTES les catégories),
puis on ajoute les relations IN_CATEGORY manquantes et on met à jour
la propriété b.categories.

Idempotent (MERGE partout) : rejouable sans risque.

    cd backend
    python repair_categories.py

Durée : ~1 requête Google Books par livre. Pour 2000 livres avec la pause
de 0.4s, compter ~15-20 min. Le script reprend là où il s'était arrêté
si on le relance (les livres déjà enrichis sont marqués categories_fixed).
"""
import time

from google_books import get_book_by_id
from neo4j_client import get_driver

PAUSE_SECONDS = 0.4  # ménage le quota Google Books


def fetch_book_ids(session) -> list[str]:
    result = session.run(
        "MATCH (b:Book) WHERE b.categories_fixed IS NULL "
        "RETURN b.external_id AS id"
    )
    return [record["id"] for record in result]


def update_book_categories(session, external_id: str, categories: list[str]):
    session.run(
        """
        MATCH (b:Book {external_id: $external_id})
        SET b.categories = $categories_str,
            b.categories_fixed = true
        WITH b
        UNWIND $category_list AS category_name
        MERGE (c:Category {name: category_name})
        MERGE (b)-[:IN_CATEGORY]->(c)
        """,
        external_id=external_id,
        categories_str=", ".join(categories),
        category_list=categories,
    )


def mark_done(session, external_id: str):
    """Marque un livre comme traité même sans nouvelle catégorie
    (livre disparu de l'API, ou détail sans catégories)."""
    session.run(
        "MATCH (b:Book {external_id: $external_id}) SET b.categories_fixed = true",
        external_id=external_id,
    )


def main():
    driver = get_driver()
    with driver.session() as session:
        book_ids = fetch_book_ids(session)
        print(f"{len(book_ids)} livres à enrichir.\n")

        for i, external_id in enumerate(book_ids, start=1):
            try:
                detail = get_book_by_id(external_id)
            except Exception as e:
                print(f"[{i}/{len(book_ids)}] {external_id} : erreur {e} — on passera au prochain run")
                time.sleep(PAUSE_SECONDS)
                continue

            categories = [
                c.strip()
                for c in (detail.get("categories") or "").split(",")
                if c.strip()
            ] if detail else []

            if categories:
                update_book_categories(session, external_id, categories)
                print(f"[{i}/{len(book_ids)}] {external_id} -> {categories}")
            else:
                mark_done(session, external_id)
                print(f"[{i}/{len(book_ids)}] {external_id} -> aucune catégorie côté détail")

            time.sleep(PAUSE_SECONDS)

    print("\nTerminé. Vérification rapide dans Neo4j Browser :")
    print("  MATCH (b:Book)-[:IN_CATEGORY]->(c) RETURN b.title, collect(c.name) LIMIT 20")
    driver.close()


if __name__ == "__main__":
    main()
