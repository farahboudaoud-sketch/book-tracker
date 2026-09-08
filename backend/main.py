from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Book, UserBook
from schemas import AddBookIn, UpdateProgressIn, LibraryEntryOut, BookOut
from google_books import search_books
from recommend import get_recommendations

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mon suivi de lecture")

# En prod, remplacez "*" par l'URL exacte de votre frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/search")
def search(q: str):
    if not q.strip():
        raise HTTPException(400, "Le paramètre 'q' est requis")
    return search_books(q, max_results=12)


@app.get("/api/library", response_model=list[LibraryEntryOut])
def get_library(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(UserBook).join(Book, UserBook.book_id == Book.id)
    if status:
        query = query.filter(UserBook.status == status)
    entries = query.order_by(UserBook.added_at.desc()).all()
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


@app.post("/api/library", response_model=LibraryEntryOut)
def add_to_library(payload: AddBookIn, db: Session = Depends(get_db)):
    book = db.query(Book).filter(Book.external_id == payload.external_id).first()
    if not book:
        book = Book(
            external_id=payload.external_id,
            title=payload.title,
            authors=payload.authors,
            categories=payload.categories,
            thumbnail=payload.thumbnail,
            published_year=payload.published_year,
        )
        db.add(book)
        db.commit()
        db.refresh(book)

    existing = db.query(UserBook).filter(UserBook.book_id == book.id).first()
    if existing:
        raise HTTPException(409, "Ce livre est déjà dans votre bibliothèque")

    entry = UserBook(
        book_id=book.id,
        status=payload.status,
        total_pages=payload.total_pages,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return LibraryEntryOut(
        id=entry.id, status=entry.status, current_page=entry.current_page,
        total_pages=entry.total_pages, rating=entry.rating, notes=entry.notes,
        added_at=entry.added_at, finished_at=entry.finished_at,
        book=BookOut.model_validate(book),
    )


@app.patch("/api/library/{entry_id}", response_model=LibraryEntryOut)
def update_progress(entry_id: int, payload: UpdateProgressIn, db: Session = Depends(get_db)):
    entry = db.query(UserBook).get(entry_id)
    if not entry:
        raise HTTPException(404, "Entrée introuvable")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(entry, field, value)

    if data.get("status") == "read" and not entry.finished_at:
        entry.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(entry)
    book = db.query(Book).get(entry.book_id)
    return LibraryEntryOut(
        id=entry.id, status=entry.status, current_page=entry.current_page,
        total_pages=entry.total_pages, rating=entry.rating, notes=entry.notes,
        added_at=entry.added_at, finished_at=entry.finished_at,
        book=BookOut.model_validate(book),
    )


@app.delete("/api/library/{entry_id}")
def remove_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(UserBook).get(entry_id)
    if not entry:
        raise HTTPException(404, "Entrée introuvable")
    db.delete(entry)
    db.commit()
    return {"ok": True}


@app.get("/api/recommendations")
def recommendations(db: Session = Depends(get_db)):
    return get_recommendations(db, limit=10)


# Sert le frontend statique (index.html, style.css, app.js) sur la racine "/"
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
