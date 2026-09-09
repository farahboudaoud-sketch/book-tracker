from datetime import datetime, timezone
from html import escape

from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Book, UserBook
from schemas import AddBookIn, UpdateProgressIn, LibraryEntryOut, BookOut
from google_books import search_books, get_book_by_id
from recommend import get_recommendations


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mon suivi de lecture")


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# RECHERCHE GOOGLE BOOKS
# ---------------------------------------------------------

@app.get("/api/search")
def search(q: str):
    if not q.strip():
        raise HTTPException(400, "Le paramètre 'q' est requis")

    return search_books(q, max_results=12)


# ---------------------------------------------------------
# BIBLIOTHÈQUE
# ---------------------------------------------------------

@app.get("/api/library", response_model=list[LibraryEntryOut])
def get_library(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(UserBook).join(
        Book,
        UserBook.book_id == Book.id
    )

    if status:
        query = query.filter(UserBook.status == status)

    entries = query.order_by(
        UserBook.added_at.desc()
    ).all()

    result = []

    for entry in entries:
        book = db.query(Book).get(entry.book_id)

        result.append(
            LibraryEntryOut(
                id=entry.id,
                status=entry.status,
                current_page=entry.current_page,
                total_pages=entry.total_pages,
                rating=entry.rating,
                notes=entry.notes,
                added_at=entry.added_at,
                finished_at=entry.finished_at,
                book=BookOut.model_validate(book),
            )
        )

    return result


# ---------------------------------------------------------
# AJOUTER UN LIVRE À LA BIBLIOTHÈQUE
# ---------------------------------------------------------

@app.post("/api/library", response_model=LibraryEntryOut)
def add_to_library(
    payload: AddBookIn,
    db: Session = Depends(get_db)
):

    # Vérifier que le statut est valide
    if payload.status not in ["to_read", "reading", "read"]:
        raise HTTPException(
            400,
            "Statut invalide"
        )

    book = db.query(Book).filter(
        Book.external_id == payload.external_id
    ).first()

    # Le livre n'existe pas encore en base
    if not book:

        book = Book(
            external_id=payload.external_id,
            title=payload.title,
            authors=payload.authors,
            categories=payload.categories,
            thumbnail=payload.thumbnail,
            published_year=payload.published_year,
            description=payload.description,
        )

        db.add(book)
        db.commit()
        db.refresh(book)

    # Vérifier qu'il n'est pas déjà dans la bibliothèque
    existing = db.query(UserBook).filter(
        UserBook.book_id == book.id
    ).first()

    if existing:
        raise HTTPException(
            409,
            "Ce livre est déjà dans votre bibliothèque"
        )

    # Créer l'entrée bibliothèque
    entry = UserBook(
        book_id=book.id,
        status=payload.status,
        total_pages=payload.total_pages,
    )

    # Si le livre est directement marqué comme terminé
    if payload.status == "read":
        entry.finished_at = datetime.now(timezone.utc)

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return LibraryEntryOut(
        id=entry.id,
        status=entry.status,
        current_page=entry.current_page,
        total_pages=entry.total_pages,
        rating=entry.rating,
        notes=entry.notes,
        added_at=entry.added_at,
        finished_at=entry.finished_at,
        book=BookOut.model_validate(book),
    )


# ---------------------------------------------------------
# MODIFIER LA PROGRESSION
# ---------------------------------------------------------

@app.patch(
    "/api/library/{entry_id}",
    response_model=LibraryEntryOut
)
def update_progress(
    entry_id: int,
    payload: UpdateProgressIn,
    db: Session = Depends(get_db)
):

    entry = db.query(UserBook).get(entry_id)

    if not entry:
        raise HTTPException(
            404,
            "Entrée introuvable"
        )

    data = payload.model_dump(
        exclude_unset=True
    )

    for field, value in data.items():
        setattr(entry, field, value)

    # Si le livre passe à "Terminé"
    if data.get("status") == "read" and not entry.finished_at:
        entry.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(entry)

    book = db.query(Book).get(entry.book_id)

    return LibraryEntryOut(
        id=entry.id,
        status=entry.status,
        current_page=entry.current_page,
        total_pages=entry.total_pages,
        rating=entry.rating,
        notes=entry.notes,
        added_at=entry.added_at,
        finished_at=entry.finished_at,
        book=BookOut.model_validate(book),
    )


# ---------------------------------------------------------
# SUPPRIMER UN LIVRE
# ---------------------------------------------------------

@app.delete("/api/library/{entry_id}")
def remove_entry(
    entry_id: int,
    db: Session = Depends(get_db)
):

    entry = db.query(UserBook).get(entry_id)

    if not entry:
        raise HTTPException(
            404,
            "Entrée introuvable"
        )

    db.delete(entry)
    db.commit()

    return {"ok": True}


# ---------------------------------------------------------
# RECOMMANDATIONS
# ---------------------------------------------------------

@app.get("/api/recommendations")
def recommendations(
    db: Session = Depends(get_db)
):
    return get_recommendations(
        db,
        limit=10
    )


# ---------------------------------------------------------
# PAGE DE DÉTAIL D'UN LIVRE
# ---------------------------------------------------------

@app.get(
    "/book/{external_id}",
    response_class=HTMLResponse
)
def book_detail(external_id: str):

    book = get_book_by_id(external_id)

    if not book:
        raise HTTPException(
            404,
            "Livre introuvable"
        )

    title = escape(
        book.get("title") or "Titre inconnu"
    )

    authors = escape(
        book.get("authors") or "Auteur inconnu"
    )

    categories = escape(
        book.get("categories") or ""
    )

    thumbnail = escape(
        book.get("thumbnail") or ""
    )

    description = escape(
        book.get("description")
        or "Aucune description disponible."
    )

    published_year = escape(
        book.get("published_year") or ""
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">

    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>{title} - Carnet de lecture</title>

        <link
            rel="stylesheet"
            href="/style.css"
        >
    </head>

    <body>

        <div class="app">

            <header class="topbar">

                <h1>Carnet de lecture</h1>

            </header>

            <main>

                <a
                    href="/"
                    class="back-link"
                >
                    ← Retour
                </a>

                <section class="book-detail">

                    <div class="book-detail-cover">

                        <img
                            src="{thumbnail}"
                            alt="{title}"
                        >

                    </div>


                    <div class="book-detail-info">

                        <h2>
                            {title}
                        </h2>

                        <p class="book-detail-authors">
                            {authors}
                        </p>

                        {
                            f'<p class="book-detail-year">{published_year}</p>'
                            if published_year
                            else ""
                        }

                        {
                            f'<p class="book-detail-categories">{categories}</p>'
                            if categories
                            else ""
                        }


                        <div class="book-description">

                            <h3>
                                Description
                            </h3>

                            <p>
                                {description}
                            </p>

                        </div>


                        <form
                            action="/book/{external_id}/add"
                            method="post"
                            class="add-book-form"
                        >

                            <label for="status">
                                Ajouter à ma bibliothèque
                            </label>


                            <select
                                name="status"
                                id="status"
                            >

                                <option value="to_read">
                                    À lire
                                </option>

                                <option value="reading">
                                    En cours
                                </option>

                                <option value="read">
                                    Terminé
                                </option>

                            </select>


                            <button
                                type="submit"
                                class="action-btn"
                            >
                                Ajouter à ma bibliothèque
                            </button>

                        </form>

                    </div>

                </section>

            </main>

        </div>

    </body>

    </html>
    """

    return HTMLResponse(content=html)


# ---------------------------------------------------------
# AJOUT D'UN LIVRE DEPUIS SA PAGE DE DÉTAIL
# ---------------------------------------------------------

@app.post(
    "/book/{external_id}/add"
)
def add_book_from_detail(
    external_id: str,
    status: str = Form(...),
    db: Session = Depends(get_db)
):

    # Vérifier le statut
    if status not in [
        "to_read",
        "reading",
        "read"
    ]:
        raise HTTPException(
            400,
            "Statut invalide"
        )

    # Récupérer le livre depuis Google Books
    book_data = get_book_by_id(external_id)

    if not book_data:
        raise HTTPException(
            404,
            "Livre introuvable"
        )

    # Chercher le livre dans notre base
    book = db.query(Book).filter(
        Book.external_id == external_id
    ).first()

    # S'il n'existe pas encore
    if not book:

        book = Book(
            external_id=book_data["external_id"],
            title=book_data.get(
                "title",
                "Titre inconnu"
            ),
            authors=book_data.get(
                "authors",
                ""
            ),
            categories=book_data.get(
                "categories",
                ""
            ),
            thumbnail=book_data.get(
                "thumbnail"
            ),
            published_year=book_data.get(
                "published_year"
            ),
            description=book_data.get(
                "description"
            ),
        )

        db.add(book)
        db.commit()
        db.refresh(book)

    # Vérifier si le livre est déjà présent
    existing = db.query(UserBook).filter(
        UserBook.book_id == book.id
    ).first()

    if existing:
        raise HTTPException(
            409,
            "Ce livre est déjà dans votre bibliothèque"
        )

    # Créer l'entrée
    entry = UserBook(
        book_id=book.id,
        status=status,
        total_pages=0,
    )

    # Si directement terminé
    if status == "read":
        entry.finished_at = datetime.now(
            timezone.utc
        )

    db.add(entry)
    db.commit()

    # Retour à l'accueil
    return RedirectResponse(
        url="/",
        status_code=303
    )


# ---------------------------------------------------------
# FRONTEND STATIQUE
# ---------------------------------------------------------

app.mount(
    "/",
    StaticFiles(
        directory="../frontend",
        html=True
    ),
    name="frontend"
)