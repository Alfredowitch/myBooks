"""
DATEI: open_library.py
PROJEKT: MyBook-Management (v1.3.0)
BESCHREIBUNG: Kümmert sich um die Daten von Open Library via ISBN oder Autor Titel zu finden.
              Holt das Rating-ol, Rating Count-ol und Description und evtl. ISBN.
              Falls Description von Google schon gefüllt ist, oder manuell erstellt wurde
              Schreiben wir die OpenLibrary Description in das Feld Notes.
"""
import requests
from tqdm import tqdm

from Gemini.file_utils import clean_description

OL_API_URL = "https://openlibrary.org/api/books"
OL_SEARCH_URL = "https://openlibrary.org/search.json"


def fetch_open_library_data(title, authors, isbn=None):
    """
    Sucht bei Open Library. Erst via ISBN, dann via Suche.
    """
    # 1. Direkter Weg (Deine funktionierende URL)
    if isbn and len(str(isbn)) in (10, 13):
        return _get_details_via_api(isbn)

    # 2. Such-Weg (Falls keine ISBN da ist)
    if title:
        author_name = authors[0][1] if authors else ""
        try:
            # Wir suchen nach Titel und Autor
            params = {'q': f'title:{title} author:{author_name}', 'limit': 1}
            resp = requests.get(OL_SEARCH_URL, params=params, timeout=10)
            data = resp.json()

            if data.get('docs'):
                # Wir nehmen die erste ISBN, die wir im Treffer finden
                found_isbns = data['docs'][0].get('isbn', [])
                if found_isbns:
                    return _get_details_via_api(found_isbns[0])
        except Exception as e:
            tqdm.write(f"  WARN: OL Suche fehlgeschlagen: {e}")

    return None


def _get_details_via_api(isbn):
    """Deine bewährte Logik zum Abrufen der Daten."""
    url = f"{OL_API_URL}?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        ol_key = f'ISBN:{isbn}'
        book_info = data.get(ol_key, {})
        if not book_info:
            return None

        # Beschreibung extrahieren (kann String oder Dict sein)
        raw_desc = book_info.get('description', "")
        description = raw_desc.get('value', raw_desc) if isinstance(raw_desc, dict) else raw_desc

        # Ratings extrahieren
        details = book_info.get('details', book_info)
        rating_data = details.get('ratings', {})

        return {
            'ol_isbn': isbn,
            'description': description,
            'ol_rating': rating_data.get('average'),
            'ol_count': rating_data.get('count')
        }
    except Exception:
        return None

# Mein Funktion für die API
def enrich_from_open_library(book_data):
    """
    Ergänzt Daten von Open Library direkt im übergebenen book_data Objekt.
    """
    # 1. API Abfrage
    ol_raw = fetch_open_library_data(book_data.title, book_data.authors, book_data.isbn)

    if not ol_raw or not isinstance(ol_raw, dict):
        return  book_data # Nichts gefunden, wir brechen ab

    # 2. ISBN ergänzen, falls sie noch fehlt
    if not book_data.isbn and ol_raw.get('ol_isbn'):
        book_data.isbn = ol_raw['ol_isbn']

    # 3. Ratings (direkte Zuweisung in die spezifischen OL-Felder)
    book_data.rating_ol = ol_raw.get('ol_rating') or 0.0
    book_data.ratings_count_ol = ol_raw.get('ol_count') or 0

    # 4. Beschreibung / Notizen
    ol_desc = ol_raw.get('description')
    if ol_desc and isinstance(ol_desc, str):
        clean_ol_desc = clean_description(ol_desc)

        # Falls das Hauptfeld leer ist:
        if not book_data.description and not getattr(book_data, 'is_manual_description', 0):
            book_data.description = clean_ol_desc
        else:
            # Als Notiz ergänzen, wenn nicht schon vorhanden
            current_notes = book_data.notes or ""
            if clean_ol_desc[:100] not in current_notes:
                header = "\n--- INFO (Open Library) ---\n"
                book_data.notes = (current_notes + header + clean_ol_desc).strip()

    # Am Ende geben wir das Objekt (verändert oder unverändert) zurück
    return book_data

# -------------------------------------------------------------------------
# if __name__ == "__main__":
#     # Beispiel-Daten: ISBN vorhanden, Ratings fehlen
#     test_data = {
#         'isbn': '9783596181971', # Beispiel-ISBN für einen Apps
#         'average_rating': None,
#         'ratings_count': None,
#     }
#
#     updated_data = read_open_library(test_data)
#     import pprint
#     pprint.pprint(updated_data)