import os
import httpx

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY")  # optionnel, augmente juste le quota


def _parse_item(item: dict) -> dict:
    info = item.get("volumeInfo", {})
    images = info.get("imageLinks", {})
    return {
        "external_id": item.get("id"),
        "title": info.get("title", "Titre inconnu"),
        "authors": ", ".join(info.get("authors", [])),
        "categories": ", ".join(info.get("categories", [])),
        "thumbnail": images.get("thumbnail"),
        "published_year": (info.get("publishedDate") or "")[:4],
        "description": info.get("description"),
    }


def search_books(query: str, max_results: int = 10, start_index: int = 0) -> list[dict]:
    params = {"q": query, "maxResults": max_results, "startIndex": start_index}
    if API_KEY:
        params["key"] = API_KEY
    with httpx.Client(timeout=10) as client:
        resp = client.get(GOOGLE_BOOKS_API, params=params)
        resp.raise_for_status()
        data = resp.json()
    return [_parse_item(item) for item in data.get("items", [])]


def get_book_by_id(external_id: str) -> dict | None:
    """Récupère un livre précis via l'endpoint dédié /volumes/{id}.
    Contrairement à search_books, ceci fonctionne avec un vrai ID Google Books
    (la recherche q=id:... n'est pas un opérateur supporté par l'API)."""
    params = {}
    if API_KEY:
        params["key"] = API_KEY
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{GOOGLE_BOOKS_API}/{external_id}", params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return _parse_item(resp.json())