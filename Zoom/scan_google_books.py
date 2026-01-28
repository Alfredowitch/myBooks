"""
DATEI: google_books.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Greift auf die Google Books API zu. Liefert Daten im Format für BookTData.
              Unterstützt ISBN-Suche via Titel/Autor, falls keine ISBN vorhanden ist.
"""
import requests
import re
from typing import Optional, Dict, Any, List
from Zoom.utils import clean_description

# Basis-URL für die Google Books API
SEARCH_URL = "https://www.googleapis.com/books/v1/volumes"


def _extract_prioritized_isbn(industry_identifiers: List[Dict[str, str]]) -> Optional[str]:
    """Extrahiert bevorzugt ISBN-13, sonst ISBN-10."""
    isbn_13 = None
    isbn_10 = None

    for identifier in industry_identifiers:
        id_type = identifier.get('type')
        isbn = identifier.get('identifier')
        if not isbn: continue

        isbn_clean = re.sub(r'[\s\-]', '', str(isbn))
        if id_type == 'ISBN_13' and len(isbn_clean) == 13:
            isbn_13 = isbn_clean
        elif id_type == 'ISBN_10' and len(isbn_clean) in (10, 13):
            isbn_10 = isbn_clean

    return isbn_13 or isbn_10


def _query_api(params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Führt den eigentlichen HTTP-Request aus."""
    try:
        response = requests.get(SEARCH_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get('totalItems', 0) > 0 and data.get('items'):
            return data['items'][0]
    except Exception as e:
        print(f"  [API] Google Books Fehler: {e}")
    return None


def search_isbn(title: str, author_lastname: str, lang: Optional[str] = None) -> Optional[str]:
    """Sucht eine ISBN basierend auf Titel und Autor."""
    if not title: return None

    # Suche mit expliziten Feldern für höhere Genauigkeit
    query = f"intitle:\"{title}\""
    if author_lastname and author_lastname != "Unbekannt":
        query += f" inauthor:\"{author_lastname}\""

    params = {'q': query, 'maxResults': 1}
    if lang: params['langRestrict'] = lang

    item = _query_api(params)
    if item:
        volume_info = item.get('volumeInfo', {})
        return _extract_prioritized_isbn(volume_info.get('industryIdentifiers', []))
    return None


def fetch_metadata(isbn: str = None, title: str = None, author: str = None, lang: str = None) -> Dict[str, Any]:
    """
    Sucht bei Google Books und liefert ein Dictionary zurück,
    das direkt via merge_with in BookTData integriert werden kann.
    """
    item = None
    if isbn:
        item = _query_api({'q': f"isbn:{isbn}", 'maxResults': 1})

    if not item and title:
        # Falls ISBN-Suche fehlschlug oder keine ISBN da war: Suche über Titel/Autor
        query = f"intitle:\"{title}\""
        if author: query += f" inauthor:\"{author}\""
        item = _query_api({'q': query, 'maxResults': 1})

    if not item:
        return {}

    info = item.get('volumeInfo', {})
    published_date = info.get('publishedDate', "")
    clean_year = ""
    if published_date:
        match = re.search(r'\d{4}', published_date)
        if match:
            clean_year = match.group(0)

    # Vorbereitung der Autoren als Liste von Tupeln (firstname, lastname)
    google_authors = []
    for full_name in info.get('authors', []):
        parts = full_name.split()
        if len(parts) > 1:
            google_authors.append((" ".join(parts[:-1]), parts[-1]))
        else:
            google_authors.append(("", parts[0]))

    # Mapping auf BookTData Attribute
    # Wir liefern nur Daten, die für ein merge_with sinnvoll sind
    metadata = {
        "isbn": _extract_prioritized_isbn(info.get('industryIdentifiers', [])),
        "rating_g": float(info.get('averageRating', 0.0)),
        "rating_g_count": int(info.get('ratingsCount', 0)),
        "description": clean_description(info.get('description', "")),
        "year": clean_year,
        "language": info.get('language'),
        "keywords": info.get('categories', []),
        "authors": google_authors  # Wird nur übernommen, wenn BookTData.authors leer ist
    }

    return {k: v for k, v in metadata.items() if v}


def get_google_data(junior: Any) -> Dict[str, Any]:
    """
    Spezifischer Helper für den Junior (BookTData).
    Prüft fehlende ISBN und bereitet den API-Merge vor.
    """
    # 1. ISBN besorgen, falls sie fehlt
    current_isbn = junior.isbn
    author_lastname = junior.authors[0][1] if junior.authors else ""

    if not current_isbn and junior.title:
        current_isbn = search_isbn(junior.title, author_lastname, junior.language)

    if not current_isbn and not junior.title:
        return {}

    # 2. Details abrufen
    api_results = fetch_metadata(
        isbn=current_isbn,
        title=junior.title,
        author=author_lastname,
        lang=junior.language
    )

    # 3. Defensive Bereinigung vor dem Merge:
    # Autoren nur mitschicken, wenn der Junior noch keine hat
    if junior.authors and "authors" in api_results:
        del api_results["authors"]

    # Beschreibung nur mitschicken, wenn noch keine da ist oder nicht manuell
    if (junior.description or getattr(junior, 'is_manual_description', 0)) and "description" in api_results:
        del api_results["description"]


    # --- 🕵️ DER ENTSCHEIDENDE DEBUG-CHECK ---
    if api_results:
        print("\n--- 🌐 Google Books API RAW DATA ---")
        for k, v in api_results.items():
            print(f"KEY: {k:<15} | VAL: {v} (Typ: {type(v).__name__})")
        print("------------------------------------\n")
    # --- DEBUG ENDE ---

    return api_results