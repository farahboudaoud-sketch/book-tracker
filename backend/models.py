from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func
from database import Base


class Book(Base):
    """Un livre tel que décrit par Google Books / Open Library (métadonnées seules)."""
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True, nullable=False)  # id Google Books
    title = Column(String, nullable=False)
    authors = Column(String, default="")       # "Auteur A, Auteur B"
    categories = Column(String, default="")    # "Fiction, Fantasy"
    thumbnail = Column(String, nullable=True)
    published_year = Column(String, nullable=True)
    description = Column(Text, nullable=True)


class UserBook(Base):
    """Le suivi personnel d'un livre : statut, progression, note."""
    __tablename__ = "user_books"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, nullable=False, index=True)
    status = Column(String, default="to_read")  # to_read | reading | read
    current_page = Column(Integer, default=0)
    total_pages = Column(Integer, default=0)
    rating = Column(Integer, nullable=True)      # 1 à 5, rempli quand status == read
    notes = Column(Text, nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
