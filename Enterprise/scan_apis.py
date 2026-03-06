import requests
import re
import html
from typing import Optional, Dict, Any, List

# --- KONFIGURATION ---
GOOGLE_URL = "https://www.googleapis.com/books/v1/volumes"
OL_URL = "https://openlibrary.org/search.json"

# --- INTERNE HELFER (früher in utils) ---
def clean_html(raw_text: str) -> str:
    if not raw_text: return ""
    clean = html.unescape(raw_text)
    clean = re.sub(r'<[^>]+>', '', clean)
    return clean.strip()

def extract_isbn(industry_identifiers: List[Dict]) -> Optional[str]:
    """Extrahiert ISBN-13 oder ISBN-10 aus Google-Daten."""
    for idnt in industry_identifiers:
        if idnt.get('type') in ['ISBN_13', 'ISBN_10']:
            return re.sub(r'[\s\-]', '', str(idnt.get('identifier', '')))
    return None

# --- GOOGLE BOOKS LOGIK ---
def fetch_google(title: str, author: str, isbn: str = None) -> Dict[str, Any]:
    params = {'maxResults': 1}
    if isbn:
        params['q'] = f"isbn:{isbn}"
    else:
        params['q'] = f"intitle:{title} inauthor:{author}"

    try:
        resp = requests.get(GOOGLE_URL, params=params, timeout=5)
        data = resp.json()
        if data.get('totalItems', 0) > 0:
            info = data['items'][0]['volumeInfo']
            return {
                'rating_g': float(info.get('averageRating', 0.0)),
                'rating_g_count': int(info.get('ratingsCount', 0)),
                'description': clean_html(info.get('description', "")),
                'keywords': info.get('categories', []),
                'isbn': extract_isbn(info.get('industryIdentifiers', []))
            }
    except Exception as e:
        print(f"  [Sensor] Google Fehler: {e}")
    return {}

# --- OPEN LIBRARY LOGIK ---
def fetch_openlibrary(title: str, author: str, isbn: str = None) -> Dict[str, Any]:
    params = {'limit': 1}
    if isbn:
        params['q'] = f"isbn:{isbn}"
    else:
        params['q'] = f"title:{title} author:{author}"

    try:
        resp = requests.get(OL_URL, params=params, timeout=5)
        data = resp.json()
        if data.get('numFound', 0) > 0:
            doc = data['docs'][0]
            return {
                'rating_ol': doc.get('ratings_average', 0.0),
                'description': " ".join(doc.get('first_sentence', [])) or ""
            }
    except Exception as e:
        print(f"  [Sensor] OpenLibrary Fehler: {e}")
    return {}

# --- DER HAUPT-VERTEILER (Die einzige Funktion, die Scotty ruft) ---
def fetch_all_metadata(title: str, authors_list: list, isbn: str = None) -> Dict[str, Any]:
    """
    Kombiniert alle API-Quellen zu einem Paket.
    authors_list: Erwartet [(Vorname, Nachname)]
    """
    main_author = authors_list[0][1] if authors_list else ""
    results = {}

    # 1. Google Books (Primärquelle)
    g_data = fetch_google(title, main_author, isbn)
    if g_data:
        results.update(g_data)

    # 2. OpenLibrary (Ergänzung)
    ol_data = fetch_openlibrary(title, main_author, isbn or results.get('isbn'))
    if ol_data:
        results['rating_ol'] = ol_data.get('rating_ol')
        # Falls Google keine Beschreibung hatte, nimm die von OL
        if not results.get('description'):
            results['description'] = ol_data.get('description')

    return results