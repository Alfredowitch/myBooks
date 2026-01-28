"""
DATEI: google_books.py
PROJEKT: MyBook-Management (v1.3.0)
BESCHREIBUNG: Kümmert sich um den API Zugriff auf Google-Books mit ISBN (aus epub).
              Liest Rating, Rating-count und Description.
"""
import requests
import re
from typing import Optional, Dict, Any, List
from tqdm import tqdm
import requests
from Gemini.file_utils import clean_description

# Basis-URL für die Google Books API
SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"


# --- Hilfsfunktionen (Optimiert) ---
def _extract_prioritized_isbn(industry_identifiers: List[Dict[str, str]]) -> Optional[str]:
    """Extrahiert die ISBN-13 (bevorzugt) oder ISBN-10."""
    isbn_13 = None
    isbn_10 = None

    for identifier in industry_identifiers:
        id_type = identifier.get('type')
        isbn = identifier.get('identifier')

        if isbn:
            isbn_clean = re.sub(r'[\s\-]', '', str(isbn))

            if id_type == 'ISBN_13' and len(isbn_clean) == 13:
                isbn_13 = isbn_clean
            elif id_type == 'ISBN_10' and len(isbn_clean) in (10, 13):
                isbn_10 = isbn_clean

    return isbn_13 if isbn_13 else isbn_10


def _query_google_books(query: str, max_results: int = 1, lang: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Generische API-Abfrage-Funktion."""
    params = {'q': query, 'maxResults': max_results}
    if lang:
        params['langRestrict'] = lang

    try:
        response = requests.get(SEARCH_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('totalItems', 0) > 0 and data.get('items'):
            return data['items'][0]
    except requests.exceptions.RequestException as e:
        tqdm.write(f"  WARN: Google Books API-Fehler ({query}): {e}")
    except Exception as e:
        tqdm.write(f"  WARN: Allgemeiner Google Books Fehler: {e}")

    return None


def get_book_data_by_isbn(isbn: str) -> Dict[str, Any]:
    """
    Ruft alle verfügbaren Metadaten von Google Books anhand der ISBN ab
    und gibt ein BookData-konformes Dictionary zurück.
    """
    if not isbn:
        return {}

    # Bereinige ISBN
    isbn_clean = re.sub(r'[\s\-]', '', isbn)
    if len(isbn_clean) not in (10, 13):
        return {}

    tqdm.write(f"  -> Google Books Suche für ISBN: {isbn_clean}")

    item = _query_google_books(query=f"isbn:{isbn_clean}", max_results=1)

    if not item:
        return {}

    volume_info = item.get('volumeInfo', {})
    published_date = volume_info.get('publishedDate')
    # Mapping auf BookData-Keys
    metadata = {
        # Ratings
        'average_rating': volume_info.get('averageRating'),
        'ratings_count': volume_info.get('ratingsCount'),

        # Inhaltliche Daten
        'description': volume_info.get('description'),
        'keywords': volume_info.get('categories', []),  # Kategorien als Keywords speichern

        # Kern-Metadaten
        'year': published_date[:4] if published_date else None,
        # Weitere Felder, die wir nicht überschreiben wollen, werden weggelassen.
    }

    # Entferne None-Werte, damit merge_with nur gefüllte Daten überschreibt
    return {k: v for k, v in metadata.items() if v is not None}


def search_isbn_only(title: str, author_lastname: str, lang: Optional[str] = None) -> Optional[str]:
    """
    Separate Funktion, um nur die ISBN zu suchen, falls sie noch fehlt.
    Diese wird in einem zukünftigen Optimierungsschritt genutzt, um ISBNs
    zu finden, wenn sie weder im Dateinamen noch im EPUB sind.
    """
    if not title or not author_lastname:
        return None

    # Suche nach ISBN, basierend auf Titel/Autor
    queries = [
        f"intitle:\"{title}\" inauthor:\"{author_lastname}\"",  # Striktere Suche
        f"{title} {author_lastname}"  # Unscharfe Suche
    ]

    tqdm.write(f"  -> Suche ISBN via Google Books: '{title}' von {author_lastname}")

    for query in queries:
        item = _query_google_books(query=query, max_results=5, lang=lang)
        if item:
            volume_info = item.get('volumeInfo', {})
            industry_ids = volume_info.get('industryIdentifiers', [])

            isbn = _extract_prioritized_isbn(industry_ids)
            if isbn:
                return isbn

    return None

# --- Haupt-API-Funktion für die Aggregation ---
def enrich_from_google_books(book_data):
    """
    Nutzt die Google Books API, um das BookData-Objekt zu vervollständigen.
    """
    # 1. ISBN-Suche, falls diese noch fehlt (Voraussetzung für get_book_data_by_isbn)
    if not book_data.isbn and book_data.title:
        # Wir nehmen den Nachnamen des ersten Autors für die Suche
        last_name = book_data.authors[0][1] if book_data.authors else ""
        if last_name != "Unbekannt":
            found_isbn = search_isbn_only(book_data.title, last_name, lang=book_data.language)
            if found_isbn:
                book_data.isbn = found_isbn

    # 2. Detail-Abfrage mit (neuer oder alter) ISBN
    if book_data.isbn:
        api_data = get_book_data_by_isbn(book_data.isbn)
        if not api_data or not isinstance(api_data, dict):
            return book_data

        # Jahr (Google ist hier meist sehr genau)
        if not book_data.year:
            book_data.year = api_data.get('year')

        # Beschreibung (nur wenn keine manuelle Beschreibung vorliegt)
        if not getattr(book_data, 'is_manual_description', 0):
            new_desc = api_data.get('description')
            if new_desc and isinstance(new_desc, str):
                # Hier nutzen wir deine clean_description Funktion aus dem Scan-Modul
                book_data.description = clean_description(new_desc)
            elif not book_data.description:
                book_data.description = ""  # Fallback auf leeren String

        # Ratings
        book_data.average_rating = api_data.get('average_rating') or book_data.average_rating
        book_data.ratings_count = api_data.get('ratings_count') or book_data.ratings_count

        # WICHTIG: Kategorien für das spätere Mapping zwischenspeichern
        # Google liefert Listen wie ["Fiction / Mystery & Detective / General"]
        if api_data.get('keywords'):
            # Wir speichern diese in einem temporären Attribut für den Single-Scan Schritt D
            if not hasattr(book_data, 'categories'):
                book_data.categories = []
            book_data.categories.extend(api_data.get('keywords'))
    # Am Ende geben wir das Objekt (verändert oder unverändert) zurück
    return book_data


def search_google_books(title: str = None, author: str = None, isbn: str = None):
    """Sucht bei Google Books und liefert ein flaches Dict für den Junior."""
    query = ""
    if isbn:
        query = f"isbn:{isbn}"
    elif title:
        query = f"intitle:{title}" + (f"+inauthor:{author}" if author else "")

    if not query: return None

    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if "items" in data:
            info = data["items"][0]["volumeInfo"]
            # Wir bauen das Dict genau so, wie Junior es erwartet
            return {
                "title": info.get("title"),
                "authors_raw": ", ".join(info.get("authors", [])),
                "description": info.get("description"),
                "isbn": next((i["identifier"] for i in info.get("industryIdentifiers", []) if i["type"] == "ISBN_13"),
                             info.get("industryIdentifiers", [{}])[0].get("identifier")),
                "language": info.get("language"),
                "categories": info.get("categories", []),
                "stars": int(info.get("averageRating", 0))
            }
    except Exception as e:
        print(f"  [API] Google Books Fehler: {e}")
    return None

# -------------------------------------------------------------------------
if __name__ == "__main__":
    # Beispiel-Aufruf der Hauptfunktion
    test_isbn = "9783518464670"  # Beispiel ISBN

    api_data = get_book_data_by_isbn(test_isbn)
    import pprint

    pprint.pprint(api_data)

    # Beispiel für die reine ISBN-Suche
    found_isbn = search_isbn_only(title="Rue de Paradis", author_lastname="Oetker")
    tqdm.write(f"Gefundene ISBN: {found_isbn}")