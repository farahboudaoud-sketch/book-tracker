import os
import time
import httpx
from dotenv import load_dotenv


# Charge les variables présentes dans backend/.env
load_dotenv()

GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY")




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


def _get_with_retry(
    url: str,
    params: dict,
    max_retries: int = 3,
) -> httpx.Response | None:
    """
    Effectue une requête vers Google Books API.
    En cas de 429, attend puis réessaie automatiquement.
    """

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url, params=params)

            # Quota dépassé : on attend puis on réessaie
            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt

                    print(
                        f"Google Books API : quota atteint (429). "
                        f"Nouvelle tentative dans {wait_time}s..."
                    )

                    time.sleep(wait_time)
                    continue

                # Toutes les tentatives ont échoué
                print(
                    "Google Books API : quota toujours atteint "
                    "après plusieurs tentatives."
                )
                return None

            # Autres erreurs HTTP
            resp.raise_for_status()
            return resp

        except httpx.RequestError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt

                print(
                    f"Erreur réseau Google Books API : {e}. "
                    f"Nouvelle tentative dans {wait_time}s..."
                )

                time.sleep(wait_time)
                continue

            print(f"Erreur réseau Google Books API : {e}")
            return None

    return None


def search_books(
    query: str,
    max_results: int = 10,
    start_index: int = 0
) -> list[dict]:

    params = {
        "q": query,
        "maxResults": max_results,
        "startIndex": start_index,
    }

    if API_KEY:
        params["key"] = API_KEY

    resp = _get_with_retry(
        GOOGLE_BOOKS_API,
        params
    )

    if resp is None:
        return []

    data = resp.json()

    return [
        _parse_item(item)
        for item in data.get("items", [])
    ]


def get_book_by_id(external_id: str) -> dict | None:
    """
    Récupère un livre précis via l'endpoint dédié /volumes/{id}.

    Contrairement à search_books, ceci fonctionne avec un vrai
    ID Google Books (la recherche q=id:... n'est pas un opérateur
    supporté par l'API).
    """

    params = {}

    if API_KEY:
        params["key"] = API_KEY

    resp = _get_with_retry(
        f"{GOOGLE_BOOKS_API}/{external_id}",
        params
    )

    if resp is None:
        return None

    if resp.status_code == 404:
        return None

    return _parse_item(resp.json())