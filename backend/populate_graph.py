"""
Script d'ingestion : peuple Neo4j avec ~2000 livres récupérés sur Google Books,
répartis sur une large liste de catégories, avec leurs embeddings de résumé
et leurs relations vers auteurs/catégories.

⚠️ À exécuter UNE SEULE FOIS (ou ponctuellement pour enrichir le pool),
PAS à chaque appel de l'API de recommandations :

    cd backend
    python populate_graph.py

Prérequis : NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD dans backend/.env
(voir .env.example), et une instance Neo4j AuraDB Free déjà créée.
"""
import time

from google_books import search_books
from embeddings import embed_texts, EMBEDDING_DIM
from neo4j_client import get_driver

TARGET_TOTAL = 2000
RESULTS_PER_PAGE = 40  # maximum autorisé par requête sur l'API Google Books

# Liste volontairement large et variée pour obtenir un pool diversifié
CATEGORIES = [
    "Fiction", "Fantasy", "Science Fiction", "Mystery", "Romance", "Thriller",
    "Historical Fiction", "Horror", "Young Adult", "Classics", "Poetry",
    "Biography", "Self-Help", "Philosophy", "History", "Science", "Psychology",
    "Business", "Art", "Cooking", "Travel", "Health", "True Crime",
    "Graphic Novels", "Dystopian fiction", "Adventure", "Contemporary Fiction",
    "Literary Fiction", "Crime", "Fairy Tales", "Mythology", "War", "Politics",
    "Religion", "Sports", "Nature", "Technology", "Humor", "Drama",
    "Short Stories",
]


def create_schema(session):
    """Index vectoriel + contraintes d'unicité, à créer une seule fois
    (IF NOT EXISTS rend le script rejouable sans erreur)."""
    session.run(
        """
        CREATE VECTOR INDEX book_embeddings IF NOT EXISTS
        FOR (b:Book) ON (b.embedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: $dim,
            `vector.similarity_function`: 'cosine'
        }}
        """,
        dim=EMBEDDING_DIM,
    )
    session.run(
        "CREATE CONSTRAINT book_external_id IF NOT EXISTS "
        "FOR (b:Book) REQUIRE b.external_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT author_name IF NOT EXISTS "
        "FOR (a:Author) REQUIRE a.name IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT category_name IF NOT EXISTS "
        "FOR (c:Category) REQUIRE c.name IS UNIQUE"
    )


def insert_book(session, book: dict, embedding: list[float]):
    session.run(
        """
        MERGE (b:Book {external_id: $external_id})
        SET b.title = $title,
            b.authors = $authors,
            b.categories = $categories,
            b.thumbnail = $thumbnail,
            b.published_year = $published_year,
            b.description = $description,
            b.embedding = $embedding

        WITH b
        UNWIND $author_list AS author_name
        MERGE (a:Author {name: author_name})
        MERGE (b)-[:BY]->(a)

        WITH b
        UNWIND $category_list AS category_name
        MERGE (c:Category {name: category_name})
        MERGE (b)-[:IN_CATEGORY]->(c)
        """,
        external_id=book["external_id"],
        title=book["title"],
        authors=book.get("authors") or "",
        categories=book.get("categories") or "",
        thumbnail=book.get("thumbnail"),
        published_year=book.get("published_year"),
        description=book.get("description") or "",
        embedding=embedding,
        author_list=[a.strip() for a in (book.get("authors") or "").split(",") if a.strip()],
        category_list=[c.strip() for c in (book.get("categories") or "").split(",") if c.strip()],
    )


def main():
    driver = get_driver()
    seen_ids = set()
    inserted = 0

    with driver.session() as session:
        print("Création de l'index vectoriel et des contraintes...")
        create_schema(session)

        for category in CATEGORIES:
            if inserted >= TARGET_TOTAL:
                break

            for start_index in (0, RESULTS_PER_PAGE):
                if inserted >= TARGET_TOTAL:
                    break

                try:
                    results = search_books(
                        f'subject:"{category}"',
                        max_results=RESULTS_PER_PAGE,
                        start_index=start_index,
                    )
                except Exception as e:
                    print(f"  ! Erreur sur '{category}' (start={start_index}) : {e}")
                    continue

                # On ne garde que les livres avec un résumé : sans texte,
                # pas d'embedding possible, et donc pas de recommandation
                # sémantique pour ce livre.
                new_books = [
                    r for r in results
                    if r["external_id"] not in seen_ids and r.get("description")
                ]

                if not new_books:
                    continue

                embeddings = embed_texts([b["description"] for b in new_books])

                for book, embedding in zip(new_books, embeddings):
                    seen_ids.add(book["external_id"])
                    insert_book(session, book, embedding.tolist())
                    inserted += 1

                print(f"[{category}] +{len(new_books)} livres (total : {inserted}/{TARGET_TOTAL})")
                time.sleep(2)  # ménage l'API Google Books (évite le rate limiting)

    print(f"\nTerminé : {inserted} livres insérés dans Neo4j.")
    driver.close()


if __name__ == "__main__":
    main()