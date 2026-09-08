from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BookOut(BaseModel):
    id: int
    external_id: str
    title: str
    authors: str
    categories: str
    thumbnail: Optional[str] = None
    published_year: Optional[str] = None

    class Config:
        from_attributes = True


class AddBookIn(BaseModel):
    external_id: str          # id renvoyé par /api/search
    title: str
    authors: str = ""
    categories: str = ""
    thumbnail: Optional[str] = None
    published_year: Optional[str] = None
    total_pages: int = 0
    status: str = "to_read"   # to_read | reading | read


class UpdateProgressIn(BaseModel):
    status: Optional[str] = None
    current_page: Optional[int] = None
    total_pages: Optional[int] = None
    rating: Optional[int] = None
    notes: Optional[str] = None


class LibraryEntryOut(BaseModel):
    id: int
    status: str
    current_page: int
    total_pages: int
    rating: Optional[int]
    notes: Optional[str]
    added_at: datetime
    finished_at: Optional[datetime]
    book: BookOut

    class Config:
        from_attributes = True
