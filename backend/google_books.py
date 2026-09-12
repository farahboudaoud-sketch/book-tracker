import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY")  # optionnel, augmente juste le quota

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 20  # Google Books limite par tranches de temps assez courtes


def _get_with_retry(client: httpx.Client, url: str, params: dict) -> httpx.Response:
    for attempt in range(1, MAX_RETRIES + 1):
        resp = client.get(url, params=params)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp

        if attempt == MAX_RETRIES:
            resp.raise_for_status()  # on a épuisé les essais, on laisse planter proprement

        wait = RETRY_DELAY_SECONDS * attempt
        print(f"  429 reçu, nouvelle tentative dans {wait}s ({attempt}/{MAX_RETRIES})...")
        time.sleep(wait)

    raise RuntimeError("Impossible d'obtenir une réponse après plusieurs tentatives")


def _split_categories(raw_categories: list[str]) -> list[str]:
    """Google Books renvoie souvent une catégorie comme un chemin
    hiérarchique du type 'Fiction / Romance / Historical / General',
    et parfois plusieurs de ces chemins pour un même livre. On éclate
    chaque chemin sur '/' pour obtenir des catégories atomiques
    ('Fiction', 'Romance', 'Historical', 'General'), on nettoie les
    espaces, et on déduplique en gardant l'ordre d'apparition."""
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in raw_categories:
        for part in raw.split("/"):
            token = part.strip()
            if token and token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens


def _parse_item(item: dict) -> dict:
    info = item.get("volumeInfo", {})
    images = info.get("imageLinks", {})
    categories = _split_categories(info.get("categories", []))
    return {
        "external_id": item.get("id"),
        "title": info.get("title", "Titre inconnu"),
        "authors": ", ".join(info.get("authors", [])),
        "categories": ", ".join(categories),
        "thumbnail": images.get("thumbnail"),
        "published_year": (info.get("publishedDate") or "")[:4],
        "description": info.get("description"),
    }


def search_books(query: str, max_results: int = 10, start_index: int = 0) -> list[dict]:
    params = {"q": query, "maxResults": max_results, "startIndex": start_index}
    if API_KEY:
        params["key"] = API_KEY
    with httpx.Client(timeout=10) as client:
        resp = _get_with_retry(client, GOOGLE_BOOKS_API, params)
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
        url = f"{GOOGLE_BOOKS_API}/{external_id}"
        resp = client.get(url, params=params)
        if resp.status_code == 404:
            return None
        if resp.status_code == 429:
            resp = _get_with_retry(client, url, params)
        else:
            resp.raise_for_status()
        return _parse_item(resp.json())